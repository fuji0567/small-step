"""Trial work must remain non-deliverable after production is enabled."""

from datetime import timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.dependencies import AuthenticatedUser, CurrentTeacher, get_current_teacher
from app.config import Settings
from app.main import create_app
from app.models import (
    AuditEvent, Child, CloudAudioJob, EdgeDevice, Notification, NotificationStatus,
    Record, RecordingSession, School, Teacher, TeacherRole, utc_now,
)
from scripts.send_pending_line_notifications import send_due_notifications


@pytest.fixture()
def trial_client(tmp_path):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path}/trial.db", auth_mode="development",
        line_channel_access_token="test-token", recorder_enabled=True,
        recorder_session_dir=str(tmp_path / "recordings"),
        guardian_archive_enabled=True, guardian_archive_base_url="https://example.test",
    )
    app = create_app(settings)
    with TestClient(app) as client:
        school = client.post("/api/v1/schools", json={"name": "Trial school"}).json()
        teacher = client.post("/api/v1/teachers", json={
            "school_id": school["id"], "name": "Trial teacher", "email": "trial@example.test",
        }).json()
        child = client.post("/api/v1/children", json={
            "school_id": school["id"], "display_name": "Test child",
            "guardian_line_user_id": "U-test-guardian",
        }).json()
        yield client, app, settings, school, teacher, child


def mode(context, trial, *, confirmed=True):
    client, _, _, school, _, _ = context
    return client.patch(f"/api/v1/schools/{school['id']}/trial-mode", json={
        "trial_mode": trial, "delivery_confirmed": confirmed,
    })


def record(context):
    client, _, _, school, teacher, child = context
    response = client.post("/api/v1/records", json={
        "school_id": school["id"], "teacher_id": teacher["id"], "child_id": child["id"],
        "category": "injury", "confidence": 1.0, "occurred_at": utc_now().isoformat(),
        "summary": "Anonymous event",
    })
    assert response.status_code == 201
    return response.json()


def approve(context, value):
    response = context[0].post(f"/api/v1/records/{value['id']}/approve", json={})
    assert response.status_code == 200
    return context[0].get("/api/v1/notifications", params={"school_id": context[3]["id"]}).json()[0]


def test_new_school_defaults_to_trial_and_production_requires_confirmation(trial_client):
    client, app, _, school, _, _ = trial_client
    assert school["trial_mode"] is True
    assert client.get("/api/v1/auth/me").json()["trial_mode"] is True
    assert mode(trial_client, False, confirmed=False).status_code == 422
    assert client.patch(f"/api/v1/schools/{school['id']}/trial-mode", json={
        "trial_mode": False, "delivery_confirmed": "true",
    }).status_code == 422
    assert mode(trial_client, False).json()["trial_mode"] is False
    assert client.get("/api/v1/auth/me").json()["trial_mode"] is False
    assert mode(trial_client, False).status_code == 200
    with app.state.session_factory() as db:
        assert len(list(db.scalars(select(AuditEvent)))) == 1


def test_trial_approval_never_creates_a_deliverable_notification(trial_client, monkeypatch):
    client, app, settings, _, _, _ = trial_client
    value = record(trial_client)
    assert value["is_trial"] is True
    notification = approve(trial_client, value)
    assert notification["status"] == "trial"
    assert client.get("/api/v1/notifications/ready").json() == []
    assert mode(trial_client, False).status_code == 200
    calls = []
    monkeypatch.setattr("scripts.send_pending_line_notifications.push_text_message", lambda **kwargs: calls.append(kwargs))
    assert send_due_notifications(settings=settings, retry_failed=True) == (0, 0)
    assert calls == []
    assert client.get(f"/api/v1/records/{value['id']}").json()["status"] == "approved"
    with app.state.session_factory() as db:
        stored = db.get(Notification, notification["id"])
        assert stored.recipient_line_user_id is None
        assert stored.delivery_attempts == 0 and stored.sent_at is None


@pytest.mark.parametrize("operation", ["retry", "mark-sent", "schedule"])
def test_trial_notifications_cannot_be_released_by_admin_operations(trial_client, operation):
    notification = approve(trial_client, record(trial_client))
    assert mode(trial_client, False).status_code == 200
    url = f"/api/v1/notifications/{notification['id']}/{operation}"
    client = trial_client[0]
    response = client.patch(url, json={"scheduled_for": utc_now().isoformat()}) if operation == "schedule" else client.post(url, json={})
    assert response.status_code == 409


def test_switch_to_trial_permanently_protects_queued_work_and_preserves_other_schools(trial_client):
    client, app, _, school, teacher, child = trial_client
    assert mode(trial_client, False).status_code == 200
    notification = approve(trial_client, record(trial_client))
    pending = record(trial_client)
    with app.state.session_factory() as db:
        device = EdgeDevice(school_id=school["id"], teacher_id=teacher["id"], name="Test device", api_key_hash="test")
        other_school = School(name="Other live school")
        db.add_all([device, other_school])
        db.flush()
        other_teacher = Teacher(school_id=other_school.id, name="Other", email="other@example.test")
        db.add(other_teacher)
        db.flush()
        other = Record(school_id=other_school.id, teacher_id=other_teacher.id, category="growth", confidence=1,
                       occurred_at=utc_now(), summary="Other school event")
        recording = RecordingSession(school_id=school["id"], teacher_id=teacher["id"], client_session_id=str(uuid4()),
                                     expires_at=utc_now() + timedelta(hours=1))
        job = CloudAudioJob(school_id=school["id"], teacher_id=teacher["id"], child_id=child["id"], device_id=device.id,
                            storage_key="test.wav", expires_at=utc_now() + timedelta(hours=1))
        db.add_all([other, recording, job])
        db.commit()
        ids = other.id, recording.id, job.id
    assert mode(trial_client, True).status_code == 200
    assert mode(trial_client, False).status_code == 200
    with app.state.session_factory() as db:
        assert db.get(Record, pending["id"]).is_trial
        assert db.get(Notification, notification["id"]).status == NotificationStatus.trial
        assert db.get(RecordingSession, ids[1]).is_trial
        assert db.get(CloudAudioJob, ids[2]).is_trial
        assert db.get(Record, ids[0]).is_trial is False
    assert record(trial_client)["is_trial"] is False


@pytest.mark.parametrize("status,dry_run", [(NotificationStatus.pending, False), (NotificationStatus.failed, False), (NotificationStatus.pending, True)])
def test_worker_independently_blocks_trial_even_if_queue_status_is_modified(trial_client, monkeypatch, status, dry_run):
    _, app, settings, _, _, _ = trial_client
    notification = approve(trial_client, record(trial_client))
    assert mode(trial_client, False).status_code == 200
    with app.state.session_factory() as db:
        stored = db.get(Notification, notification["id"])
        stored.status = status
        stored.recipient_line_user_id = "U-test-guardian"
        db.commit()
    calls = []
    monkeypatch.setattr("scripts.send_pending_line_notifications.push_text_message", lambda **kwargs: calls.append(kwargs))
    assert send_due_notifications(settings=settings, retry_failed=True, dry_run=dry_run) == (0, 0)
    assert calls == []
    with app.state.session_factory() as db:
        assert db.get(Notification, notification["id"]).status == NotificationStatus.trial


@pytest.mark.parametrize("same_school,role", [(True, TeacherRole.teacher), (False, TeacherRole.school_admin)])
def test_mode_change_requires_admin_of_the_target_school(trial_client, same_school, role):
    _, app, _, school, _, _ = trial_client
    with app.state.session_factory() as db:
        target_school = db.get(School, school["id"])
        if not same_school:
            target_school = School(name="Other school")
            db.add(target_school)
            db.flush()
        teacher = Teacher(school_id=target_school.id, name="User", email="scope@example.test", role=role)
        db.add(teacher)
        db.commit()
        current = CurrentTeacher(user=AuthenticatedUser(id="scope", email=teacher.email), teacher=teacher, is_development=False)
    app.dependency_overrides[get_current_teacher] = lambda: current
    assert mode(trial_client, False).status_code == 403


@pytest.mark.parametrize("source_trial,school_trial", [(True, False), (False, True), (False, False)])
def test_cloud_worker_propagates_trial_provenance(trial_client, source_trial, school_trial):
    from app.cloud_audio_worker import _create_record_from_cloud_job
    from app.edge_audio import EdgeAudioCandidate

    _, app, _, school, teacher, child = trial_client
    with app.state.session_factory() as db:
        db.get(School, school["id"]).trial_mode = school_trial
        device = EdgeDevice(school_id=school["id"], teacher_id=teacher["id"], name="Test", api_key_hash="test")
        db.add(device)
        db.flush()
        job = CloudAudioJob(school_id=school["id"], teacher_id=teacher["id"], child_id=child["id"], device_id=device.id,
                            is_trial=source_trial, storage_key="test.wav", expires_at=utc_now() + timedelta(hours=1))
        db.add(job)
        db.commit()
        candidate = EdgeAudioCandidate(recordable=True, category="growth", confidence=1, summary="Anonymous event")
        value = _create_record_from_cloud_job(db=db, job=job, candidate=candidate)
        assert value.is_trial == (source_trial or school_trial)


def test_trial_records_are_excluded_from_guardian_archive_even_with_bad_sent_status(trial_client):
    client, app, _, _, _, child = trial_client
    notification = approve(trial_client, record(trial_client))
    with app.state.session_factory() as db:
        stored = db.get(Notification, notification["id"])
        stored.status = NotificationStatus.sent
        stored.sent_at = utc_now()
        db.commit()
    link = client.post("/api/v1/guardian-archive-links", json={"child_id": child["id"]})
    assert link.status_code == 201
    token = link.json()["archive_url"].split("#", 1)[1]
    response = client.get("/api/v1/guardian/archive", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200 and response.json()["notifications"] == []


def test_manual_records_and_recorder_sessions_capture_trial_mode(trial_client):
    client, _, _, school, teacher, child = trial_client
    response = client.post("/api/v1/records/manual", json={
        "school_id": school["id"], "teacher_id": teacher["id"], "child_id": child["id"],
        "category": "growth", "occurred_at": utc_now().isoformat(), "summary": "Anonymous manual event",
    })
    assert response.status_code == 201 and response.json()["is_trial"] is True
    session = client.post("/api/v1/recorder/sessions", json={"client_session_id": str(uuid4())})
    assert session.status_code == 201 and session.json()["is_trial"] is True


def test_worker_also_blocks_current_trial_school_when_record_flag_is_false(trial_client, monkeypatch):
    _, app, settings, _, _, _ = trial_client
    value = record(trial_client)
    notification = approve(trial_client, value)
    with app.state.session_factory() as db:
        db.get(Record, value["id"]).is_trial = False
        stored = db.get(Notification, notification["id"])
        stored.status = NotificationStatus.pending
        stored.recipient_line_user_id = "U-test-guardian"
        db.commit()
    calls = []
    monkeypatch.setattr("scripts.send_pending_line_notifications.push_text_message", lambda **kwargs: calls.append(kwargs))
    assert send_due_notifications(settings=settings) == (0, 0)
    assert calls == []
    with app.state.session_factory() as db:
        assert db.get(Record, value["id"]).is_trial is True
