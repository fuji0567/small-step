"""Focused API coverage for the independent /rec recorder contract."""

import hashlib
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import AuthenticatedUser, CurrentTeacher, get_current_teacher
from app.config import Settings
from app.main import create_app
from app.models import RecordingSession, RecordingSessionStatus, School, Teacher, TeacherRole, utc_now


def _upload(client: TestClient, session_id: str, sequence: int, content: bytes, *, duration_ms: int = 1_000):
    return client.put(
        f"/api/v1/recorder/sessions/{session_id}/segments/{sequence}",
        files={"file": ("client-name-is-not-retained.mp4", content, "audio/mp4")},
        data={"duration_ms": str(duration_ms), "sha256": hashlib.sha256(content).hexdigest()},
    )


def _authenticate_as(app, teacher_id: str) -> None:
    with app.state.session_factory() as db:
        teacher = db.get(Teacher, teacher_id)
    assert teacher is not None
    app.dependency_overrides[get_current_teacher] = lambda: CurrentTeacher(
        user=AuthenticatedUser(id=teacher.auth_user_id or "test-auth", email=teacher.email),
        teacher=teacher,
        is_development=False,
    )


@pytest.fixture()
def recorder_client(tmp_path: Path):
    app = create_app(
        Settings(
            database_url=f"sqlite:///{tmp_path}/recorder.db",
            auth_mode="supabase",
            recorder_enabled=True,
            recorder_session_dir=str(tmp_path / "sessions"),
        )
    )
    with TestClient(app) as client:
        with app.state.session_factory() as db:
            school = School(name="Recorder test school")
            db.add(school)
            db.flush()
            teacher = Teacher(
                school_id=school.id,
                name="Recorder teacher",
                email="recorder@example.test",
                auth_user_id="auth-recorder",
                role=TeacherRole.teacher,
            )
            other = Teacher(
                school_id=school.id,
                name="Other teacher",
                email="other@example.test",
                auth_user_id="auth-other",
                role=TeacherRole.teacher,
            )
            db.add_all([teacher, other])
            db.commit()
            db.refresh(school)
            db.refresh(teacher)
            db.refresh(other)

        current = CurrentTeacher(
            user=AuthenticatedUser(id=teacher.auth_user_id, email=teacher.email),
            teacher=teacher,
            is_development=False,
        )
        app.dependency_overrides[get_current_teacher] = lambda: current
        yield client, app, school.id, teacher.id, other.id
        app.dependency_overrides.clear()


def test_create_upload_idempotency_and_hash_conflict(recorder_client):
    client, _app, _school_id, _teacher_id, _other_id = recorder_client
    client_id = str(uuid4())
    created = client.post("/api/v1/recorder/sessions", json={"client_session_id": client_id})
    assert created.status_code == 201
    repeated = client.post("/api/v1/recorder/sessions", json={"client_session_id": client_id})
    assert repeated.status_code == 201
    assert repeated.json()["id"] == created.json()["id"]

    content = b"segment bytes"
    uploaded = _upload(client, created.json()["id"], 0, content)
    assert uploaded.status_code == 200
    assert uploaded.json()["segments"][0]["sha256"] == hashlib.sha256(content).hexdigest()
    repeated_upload = _upload(client, created.json()["id"], 0, content)
    assert repeated_upload.status_code == 200
    assert len(repeated_upload.json()["segments"]) == 1

    mismatch = client.put(
        f"/api/v1/recorder/sessions/{created.json()['id']}/segments/0",
        files={"file": ("another.mp4", b"different", "audio/mp4")},
        data={"duration_ms": "1000", "sha256": hashlib.sha256(b"different").hexdigest()},
    )
    assert mismatch.status_code == 409

    duration_conflict = _upload(client, created.json()["id"], 0, content, duration_ms=2_000)
    assert duration_conflict.status_code == 409


def test_finalize_requires_contiguous_segments_and_enforces_duration(recorder_client):
    client, _app, _school_id, _teacher_id, _other_id = recorder_client
    session = client.post("/api/v1/recorder/sessions", json={"client_session_id": str(uuid4())}).json()
    assert _upload(client, session["id"], 1, b"gap").status_code == 200
    assert client.post(f"/api/v1/recorder/sessions/{session['id']}/finalize").status_code == 409

    first = client.put(
        f"/api/v1/recorder/sessions/{session['id']}/segments/0",
        files={"file": ("first.mp4", b"first", "audio/mp4")},
        data={"duration_ms": "3600001", "sha256": hashlib.sha256(b"first").hexdigest()},
    )
    assert first.status_code == 422


def test_owner_scope_delete_and_audio_cleanup(recorder_client):
    client, app, _school_id, _teacher_id, _other_id = recorder_client
    session = client.post("/api/v1/recorder/sessions", json={"client_session_id": str(uuid4())}).json()
    assert _upload(client, session["id"], 0, b"to be deleted").status_code == 200
    session_dir = Path(app.state.settings.recorder_session_dir) / session["id"]
    assert any(session_dir.iterdir())

    # Validate owner-only access through the actual dependency using the other
    # teacher row, without exposing that row in the public response.
    with app.state.session_factory() as db:
        other_teacher = db.get(Teacher, _other_id)
    other = CurrentTeacher(
        user=AuthenticatedUser(id="auth-other", email="other@example.test"),
        teacher=other_teacher,
        is_development=False,
    )
    app.dependency_overrides[get_current_teacher] = lambda: other
    assert client.get(f"/api/v1/recorder/sessions/{session['id']}").status_code == 403
    # Restore the original owner context by looking it up from the DB.
    with app.state.session_factory() as db:
        owner = db.get(Teacher, _teacher_id)
    app.dependency_overrides[get_current_teacher] = lambda: CurrentTeacher(
        user=AuthenticatedUser(id="auth-recorder", email="recorder@example.test"),
        teacher=owner,
        is_development=False,
    )
    assert client.delete(f"/api/v1/recorder/sessions/{session['id']}").status_code == 204
    assert not session_dir.exists()
    with app.state.session_factory() as db:
        persisted = db.get(RecordingSession, session["id"])
        assert persisted.status == RecordingSessionStatus.discarded


def test_disabled_recorder_is_hidden_without_auth(tmp_path):
    app = create_app(
        Settings(database_url=f"sqlite:///{tmp_path}/disabled.db", auth_mode="supabase", recorder_enabled=False)
    )
    with TestClient(app) as client:
        assert client.post(
            "/api/v1/recorder/sessions", json={"client_session_id": str(uuid4())}
        ).status_code == 404
        assert client.get("/api/v1/recorder/sessions").status_code == 404


def test_auth_me_uses_existing_teacher_in_development(tmp_path):
    app = create_app(
        Settings(
            database_url=f"sqlite:///{tmp_path}/development-auth.db",
            auth_mode="development",
            recorder_enabled=True,
            recorder_session_dir=str(tmp_path / "sessions"),
        )
    )
    with TestClient(app) as client:
        with app.state.session_factory() as db:
            school = School(name="Development recorder school")
            db.add(school)
            db.flush()
            teacher = Teacher(
                school_id=school.id,
                name="Development recorder teacher",
                email="development-recorder@example.test",
                role=TeacherRole.teacher,
            )
            db.add(teacher)
            db.commit()
            teacher_id = teacher.id

        response = client.get("/api/v1/auth/me")

    assert response.status_code == 200
    assert response.json()["id"] == teacher_id
    assert response.json()["name"] == "Development recorder teacher"


def test_create_limits_active_drafts_but_idempotent_retry_still_succeeds(recorder_client):
    client, _app, _school_id, _teacher_id, _other_id = recorder_client
    client_ids = [str(uuid4()) for _ in range(3)]
    created = [
        client.post("/api/v1/recorder/sessions", json={"client_session_id": value})
        for value in client_ids
    ]
    assert [response.status_code for response in created] == [201, 201, 201]
    assert client.post(
        "/api/v1/recorder/sessions", json={"client_session_id": str(uuid4())}
    ).status_code == 409
    repeated = client.post(
        "/api/v1/recorder/sessions", json={"client_session_id": client_ids[0]}
    )
    assert repeated.status_code == 201
    assert repeated.json()["id"] == created[0].json()["id"]


def test_expired_draft_deletes_audio_before_rejecting_upload(recorder_client):
    client, app, _school_id, _teacher_id, _other_id = recorder_client
    session = client.post(
        "/api/v1/recorder/sessions", json={"client_session_id": str(uuid4())}
    ).json()
    assert _upload(client, session["id"], 0, b"expires").status_code == 200
    session_dir = Path(app.state.settings.recorder_session_dir) / session["id"]
    with app.state.session_factory() as db:
        persisted = db.get(RecordingSession, session["id"])
        assert persisted is not None
        persisted.expires_at = utc_now() - timedelta(seconds=1)
        db.commit()

    assert _upload(client, session["id"], 1, b"late").status_code == 409
    assert not session_dir.exists()
    with app.state.session_factory() as db:
        persisted = db.get(RecordingSession, session["id"])
        assert persisted is not None
        assert persisted.status == RecordingSessionStatus.expired


def test_list_scope_and_owner_only_detail_for_school_admin(recorder_client):
    client, app, school_id, teacher_id, other_id = recorder_client
    own = client.post(
        "/api/v1/recorder/sessions", json={"client_session_id": str(uuid4())}
    ).json()
    _authenticate_as(app, other_id)
    other = client.post(
        "/api/v1/recorder/sessions", json={"client_session_id": str(uuid4())}
    ).json()
    listed = client.get(f"/api/v1/recorder/sessions?school_id={school_id}")
    assert [item["id"] for item in listed.json()] == [other["id"]]

    with app.state.session_factory() as db:
        admin = db.get(Teacher, other_id)
        assert admin is not None
        admin.role = TeacherRole.school_admin
        db.commit()
    _authenticate_as(app, other_id)
    admin_list = client.get(f"/api/v1/recorder/sessions?school_id={school_id}")
    assert {item["id"] for item in admin_list.json()} == {own["id"], other["id"]}
    assert client.get(f"/api/v1/recorder/sessions/{own['id']}").status_code == 403
    _authenticate_as(app, teacher_id)


def test_finalize_rejects_cumulative_duration_over_limit(tmp_path):
    app = create_app(
        Settings(
            database_url=f"sqlite:///{tmp_path}/duration.db",
            auth_mode="supabase",
            recorder_enabled=True,
            recorder_session_dir=str(tmp_path / "sessions"),
            recorder_max_duration_minutes=1,
        )
    )
    with TestClient(app) as client:
        with app.state.session_factory() as db:
            school = School(name="Duration school")
            db.add(school)
            db.flush()
            teacher = Teacher(
                school_id=school.id,
                name="Duration teacher",
                email="duration@example.test",
                auth_user_id="auth-duration",
            )
            db.add(teacher)
            db.commit()
            teacher_id = teacher.id
        _authenticate_as(app, teacher_id)
        session = client.post(
            "/api/v1/recorder/sessions", json={"client_session_id": str(uuid4())}
        ).json()
        assert _upload(client, session["id"], 0, b"first", duration_ms=30_000).status_code == 200
        assert _upload(client, session["id"], 1, b"second", duration_ms=31_000).status_code == 409
        persisted = client.get(f"/api/v1/recorder/sessions/{session['id']}").json()
        assert [segment["sequence"] for segment in persisted["segments"]] == [0]


def test_finalize_succeeds_once_and_late_upload_leaves_no_new_file(recorder_client):
    client, app, _school_id, _teacher_id, _other_id = recorder_client
    session = client.post(
        "/api/v1/recorder/sessions", json={"client_session_id": str(uuid4())}
    ).json()
    assert _upload(client, session["id"], 0, b"accepted").status_code == 200
    session_dir = Path(app.state.settings.recorder_session_dir) / session["id"]
    existing_files = {path.name for path in session_dir.iterdir()}

    finalized = client.post(f"/api/v1/recorder/sessions/{session['id']}/finalize")
    assert finalized.status_code == 202
    assert finalized.json()["status"] == "queued"
    assert _upload(client, session["id"], 1, b"too late").status_code == 409
    assert {path.name for path in session_dir.iterdir()} == existing_files


def test_rejected_uploads_leave_no_audio_files(recorder_client):
    client, app, _school_id, _teacher_id, _other_id = recorder_client
    session = client.post(
        "/api/v1/recorder/sessions", json={"client_session_id": str(uuid4())}
    ).json()
    root = Path(app.state.settings.recorder_session_dir)
    malformed = client.put(
        f"/api/v1/recorder/sessions/{session['id']}/segments/0",
        files={"file": ("bad.mp4", b"bad", "audio/mp4")},
        data={"duration_ms": "1000", "sha256": "not-a-digest"},
    )
    mismatch = client.put(
        f"/api/v1/recorder/sessions/{session['id']}/segments/0",
        files={"file": ("bad.mp4", b"bad", "audio/mp4")},
        data={"duration_ms": "1000", "sha256": hashlib.sha256(b"other").hexdigest()},
    )
    unsupported = client.put(
        f"/api/v1/recorder/sessions/{session['id']}/segments/0",
        files={"file": ("bad.wav", b"bad", "audio/wav")},
        data={"duration_ms": "1000", "sha256": hashlib.sha256(b"bad").hexdigest()},
    )
    assert [malformed.status_code, mismatch.status_code, unsupported.status_code] == [422, 422, 422]
    assert not root.exists() or not any(path.is_file() for path in root.rglob("*"))
