from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.dependencies import AuthenticatedUser, CurrentTeacher, get_current_teacher
from app.config import Settings
from app.main import create_app
from app.models import (
    ClassNewsletterRecipient,
    GrowthDeliveryBatch,
    GrowthDeliveryEntry,
    Classroom,
    ClassNewsletter,
    Child,
    Notification,
    NotificationStatus,
    Record,
    RecordCategory,
    RecordStatus,
    Teacher,
    TeacherRole,
)


def _setup(client: TestClient, school_name: str = "Class delivery test") -> tuple[str, str]:
    school_response = client.post("/api/v1/schools", json={"name": school_name})
    assert school_response.status_code == 201
    school_id = school_response.json()["id"]
    activated = client.patch(
        f"/api/v1/schools/{school_id}/trial-mode",
        json={"trial_mode": False, "delivery_confirmed": True},
    )
    assert activated.status_code == 200
    teacher = client.post(
        "/api/v1/teachers", json={"school_id": school_id, "name": "先生", "email": f"{school_name}@example.com"}
    )
    assert teacher.status_code == 201
    classroom = client.post("/api/v1/classrooms", json={"school_id": school_id, "name": "年少"})
    assert classroom.status_code == 201
    configured = client.patch(
        f"/api/v1/classrooms/{classroom.json()['id']}",
        json={
            "name": "年少",
            "is_active": True,
            "delivery_enabled": True,
            "daily_growth_limit": 1,
        },
    )
    assert configured.status_code == 200
    return school_id, classroom.json()["id"]


def _child(client: TestClient, school_id: str, classroom_id: str, name: str, guardian: str | None) -> str:
    created = client.post(
        "/api/v1/children",
        json={"school_id": school_id, "display_name": name, "guardian_line_user_id": guardian},
    )
    assert created.status_code == 201
    assigned = client.put(
        f"/api/v1/children/{created.json()['id']}/classroom",
        json={"classroom_id": classroom_id},
    )
    assert assigned.status_code == 200
    return created.json()["id"]


def _growth_record(client: TestClient, school_id: str, teacher_id: str, child_id: str, summary: str) -> str:
    response = client.post(
        "/api/v1/records",
        json={
            "school_id": school_id,
            "teacher_id": teacher_id,
            "child_id": child_id,
            "category": "growth",
            "confidence": 1.0,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "summary": summary,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_class_mode_approval_waits_for_daily_selection_and_enforces_quota(tmp_path):
    app = create_app(Settings(database_url=f"sqlite:///{tmp_path}/classes.db", auth_mode="development", class_delivery_enabled=True))
    with TestClient(app) as client:
        school_id, classroom_id = _setup(client)
        teacher_id = client.get("/api/v1/teachers", params={"school_id": school_id}).json()[0]["id"]
        child_ids = [
            _child(client, school_id, classroom_id, f"園児{i}", f"U-parent-{i}")
            for i in range(3)
        ]
        record_ids = [
            _growth_record(client, school_id, teacher_id, child_id, f"成長{i}")
            for i, child_id in enumerate(child_ids)
        ]
        for record_id in record_ids:
            approved = client.post(f"/api/v1/records/{record_id}/approve", json={})
            assert approved.status_code == 200

        assert client.get("/api/v1/notifications", params={"school_id": school_id}).json() == []
        today = datetime.now(ZoneInfo("Asia/Tokyo")).date().isoformat()
        proposal = client.post(
            f"/api/v1/classrooms/{classroom_id}/growth-delivery/propose",
            json={"delivery_date": today},
        )
        assert proposal.status_code == 200, proposal.text
        assert len(proposal.json()["entries"]) == 3
        batch_id = proposal.json()["id"]

        over_limit = client.post(
            f"/api/v1/growth-delivery-batches/{batch_id}/approve",
            json={"selected_record_ids": record_ids[:2], "teacher_confirmed": True},
        )
        assert over_limit.status_code == 422
        assert client.get("/api/v1/notifications", params={"school_id": school_id}).json() == []

        selected = client.post(
            f"/api/v1/growth-delivery-batches/{batch_id}/approve",
            json={"selected_record_ids": [record_ids[1]], "teacher_confirmed": True},
        )
        assert selected.status_code == 200, selected.text
        notifications = client.get("/api/v1/notifications", params={"school_id": school_id}).json()
        assert [item["record_id"] for item in notifications] == [record_ids[1]]
        assert notifications[0]["status"] == "pending"


def test_approval_uses_the_latest_admin_configured_daily_limit(tmp_path):
    app = create_app(Settings(database_url=f"sqlite:///{tmp_path}/quota-change.db", auth_mode="development", class_delivery_enabled=True))
    with TestClient(app) as client:
        school_id, classroom_id = _setup(client, "Quota change test")
        teacher_id = client.get("/api/v1/teachers", params={"school_id": school_id}).json()[0]["id"]
        child_ids = [
            _child(client, school_id, classroom_id, f"園児{i}", f"U-quota-{i}")
            for i in range(2)
        ]
        record_ids = [
            _growth_record(client, school_id, teacher_id, child_id, f"成長{i}")
            for i, child_id in enumerate(child_ids)
        ]
        for record_id in record_ids:
            assert client.post(f"/api/v1/records/{record_id}/approve", json={}).status_code == 200

        configured = client.patch(
            f"/api/v1/classrooms/{classroom_id}",
            json={"name": "年少", "is_active": True, "delivery_enabled": True, "daily_growth_limit": 2},
        )
        assert configured.status_code == 200
        today = datetime.now(ZoneInfo("Asia/Tokyo")).date().isoformat()
        batch = client.post(
            f"/api/v1/classrooms/{classroom_id}/growth-delivery/propose",
            json={"delivery_date": today},
        ).json()
        assert batch["daily_limit"] == 2

        reduced = client.patch(
            f"/api/v1/classrooms/{classroom_id}",
            json={"name": "年少", "is_active": True, "delivery_enabled": True, "daily_growth_limit": 1},
        )
        assert reduced.status_code == 200
        over_limit = client.post(
            f"/api/v1/growth-delivery-batches/{batch['id']}/approve",
            json={"selected_record_ids": record_ids, "teacher_confirmed": True},
        )
        assert over_limit.status_code == 422
        assert client.get("/api/v1/notifications", params={"school_id": school_id}).json() == []

        approved = client.post(
            f"/api/v1/growth-delivery-batches/{batch['id']}/approve",
            json={"selected_record_ids": record_ids[:1], "teacher_confirmed": True},
        )
        assert approved.status_code == 200, approved.text
        assert approved.json()["daily_limit"] == 1


def test_empty_class_day_can_be_confirmed_with_zero_individual_messages(tmp_path):
    app = create_app(Settings(database_url=f"sqlite:///{tmp_path}/empty-class-day.db", auth_mode="development", class_delivery_enabled=True))
    with TestClient(app) as client:
        school_id, classroom_id = _setup(client, "Empty class day test")
        unassigned = client.post(
            "/api/v1/children",
            json={"school_id": school_id, "display_name": "未所属の園児"},
        )
        assert unassigned.status_code == 201
        assert unassigned.json()["classroom_id"] is None
        today = datetime.now(ZoneInfo("Asia/Tokyo")).date().isoformat()
        proposal = client.post(
            f"/api/v1/classrooms/{classroom_id}/growth-delivery/propose",
            json={"delivery_date": today},
        )
        assert proposal.status_code == 200
        assert proposal.json()["entries"] == []
        approved = client.post(
            f"/api/v1/growth-delivery-batches/{proposal.json()['id']}/approve",
            json={"selected_record_ids": [], "teacher_confirmed": True},
        )
        assert approved.status_code == 200
        assert approved.json()["status"] == "approved"
        assert client.get("/api/v1/notifications", params={"school_id": school_id}).json() == []


def test_draft_candidates_can_be_refreshed_after_more_records_are_approved(tmp_path):
    app = create_app(Settings(database_url=f"sqlite:///{tmp_path}/refresh.db", auth_mode="development", class_delivery_enabled=True))
    with TestClient(app) as client:
        school_id, classroom_id = _setup(client, "Candidate refresh test")
        teacher_id = client.get("/api/v1/teachers", params={"school_id": school_id}).json()[0]["id"]
        first_child = _child(client, school_id, classroom_id, "先の園児", "U-refresh-1")
        first_record = _growth_record(client, school_id, teacher_id, first_child, "先に承認した成長")
        assert client.post(f"/api/v1/records/{first_record}/approve", json={}).status_code == 200
        today = datetime.now(ZoneInfo("Asia/Tokyo")).date().isoformat()
        initial = client.post(
            f"/api/v1/classrooms/{classroom_id}/growth-delivery/propose",
            json={"delivery_date": today},
        ).json()
        assert len(initial["entries"]) == 1

        later_child = _child(client, school_id, classroom_id, "後の園児", "U-refresh-2")
        later_record = _growth_record(client, school_id, teacher_id, later_child, "後から承認した成長")
        assert client.post(f"/api/v1/records/{later_record}/approve", json={}).status_code == 200
        refreshed = client.post(
            f"/api/v1/growth-delivery-batches/{initial['id']}/refresh"
        )
        assert refreshed.status_code == 200, refreshed.text
        assert refreshed.json()["id"] != initial["id"]
        assert {entry["record_id"] for entry in refreshed.json()["entries"]} == {
            first_record,
            later_record,
        }


def test_fair_order_uses_accepted_count_then_oldest_delivery_then_child_id(tmp_path):
    app = create_app(Settings(database_url=f"sqlite:///{tmp_path}/fair-order.db", auth_mode="development", class_delivery_enabled=True))
    with TestClient(app) as client:
        school_id, classroom_id = _setup(client, "Fair order test")
        teacher_id = client.get("/api/v1/teachers", params={"school_id": school_id}).json()[0]["id"]
        children = [
            _child(client, school_id, classroom_id, f"園児{i}", f"U-fair-{i}")
            for i in range(5)
        ]
        candidate_records = []
        for index, child_id in enumerate(children):
            record_id = _growth_record(client, school_id, teacher_id, child_id, f"今日の成長{index}")
            assert client.post(f"/api/v1/records/{record_id}/approve", json={}).status_code == 200
            candidate_records.append(record_id)

        now = datetime.now(timezone.utc)
        sent_by_day = {
            1: now - timedelta(days=1),
            2: now - timedelta(days=2),
            3: now - timedelta(days=4),
        }
        history_deliveries = {
            children[0]: [(3, NotificationStatus.failed)],
            children[1]: [(3, NotificationStatus.sent)],
            children[2]: [(1, NotificationStatus.sent)],
            children[3]: [(1, NotificationStatus.sent), (2, NotificationStatus.sent)],
        }
        with app.state.session_factory() as db:
            for day_offset, sent_at in sent_by_day.items():
                batch = GrowthDeliveryBatch(
                    school_id=school_id,
                    classroom_id=classroom_id,
                    delivery_date=(datetime.now(ZoneInfo("Asia/Tokyo")).date() - timedelta(days=day_offset)).isoformat(),
                    daily_limit=2,
                    status="approved",
                    scheduled_for=sent_at,
                    is_trial=False,
                )
                db.add(batch)
                db.flush()
                for child_id, deliveries in history_deliveries.items():
                    status = next((status for day, status in deliveries if day == day_offset), None)
                    if status is None:
                        continue
                    # Use distinct historical records so today's candidates remain eligible.
                    from app.models import RecordCategory, RecordStatus

                    history_record = Record(
                        school_id=school_id,
                        teacher_id=teacher_id,
                        child_id=child_id,
                        category=RecordCategory.growth,
                        status=RecordStatus.approved,
                        confidence=1.0,
                        summary=f"過去の成長 {day_offset}",
                        occurred_at=sent_at - timedelta(minutes=1),
                        reviewed_at=sent_at,
                        is_trial=False,
                    )
                    db.add(history_record)
                    db.flush()
                    entry = GrowthDeliveryEntry(
                        batch_id=batch.id,
                        school_id=school_id,
                        classroom_id=classroom_id,
                        record_id=history_record.id,
                        child_id=child_id,
                        selected=True,
                    )
                    db.add(entry)
                    db.flush()
                    db.add(Notification(
                        record_id=history_record.id,
                        growth_delivery_entry_id=entry.id,
                        recipient_line_user_id=f"U-history-{child_id}",
                        scheduled_for=sent_at,
                        status=status,
                        sent_at=sent_at if status == NotificationStatus.sent else None,
                    ))
            db.commit()

        today = datetime.now(ZoneInfo("Asia/Tokyo")).date().isoformat()
        proposal = client.post(
            f"/api/v1/classrooms/{classroom_id}/growth-delivery/propose",
            json={"delivery_date": today},
        )
        assert proposal.status_code == 200, proposal.text
        ordered_child_ids = [entry["child_id"] for entry in proposal.json()["entries"]]
        expected = sorted([children[0], children[4]]) + [children[1], children[2], children[3]]
        assert ordered_child_ids == expected


def test_child_cannot_be_selected_twice_after_moving_classes_on_same_day(tmp_path):
    app = create_app(Settings(database_url=f"sqlite:///{tmp_path}/one-per-child.db", auth_mode="development", class_delivery_enabled=True))
    with TestClient(app) as client:
        school_id, first_classroom_id = _setup(client, "One per child test")
        teacher_id = client.get("/api/v1/teachers", params={"school_id": school_id}).json()[0]["id"]
        second_class = client.post(
            "/api/v1/classrooms", json={"school_id": school_id, "name": "年中"}
        ).json()
        child_id = _child(client, school_id, first_classroom_id, "園児", "U-one-per-day")
        first_record = _growth_record(client, school_id, teacher_id, child_id, "一つ目の成長")
        second_record = _growth_record(client, school_id, teacher_id, child_id, "二つ目の成長")
        for record_id in (first_record, second_record):
            assert client.post(f"/api/v1/records/{record_id}/approve", json={}).status_code == 200
        today = datetime.now(ZoneInfo("Asia/Tokyo")).date().isoformat()
        first_batch = client.post(
            f"/api/v1/classrooms/{first_classroom_id}/growth-delivery/propose",
            json={"delivery_date": today},
        ).json()
        approved = client.post(
            f"/api/v1/growth-delivery-batches/{first_batch['id']}/approve",
            json={"selected_record_ids": [first_record], "teacher_confirmed": True},
        )
        assert approved.status_code == 200, approved.text
        assert client.put(
            f"/api/v1/children/{child_id}/classroom",
            json={"classroom_id": second_class["id"]},
        ).status_code == 200
        assert client.patch(
            f"/api/v1/classrooms/{second_class['id']}",
            json={"name": "年中", "is_active": True, "delivery_enabled": True, "daily_growth_limit": 1},
        ).status_code == 200
        second_batch = client.post(
            f"/api/v1/classrooms/{second_class['id']}/growth-delivery/propose",
            json={"delivery_date": today},
        ).json()
        rejected = client.post(
            f"/api/v1/growth-delivery-batches/{second_batch['id']}/approve",
            json={"selected_record_ids": [second_record], "teacher_confirmed": True},
        )
        assert rejected.status_code == 409


def test_personal_notice_is_cancelled_after_guardian_relinks_same_account(tmp_path, monkeypatch):
    from scripts.send_pending_line_notifications import send_due_notifications

    settings = Settings(
        database_url=f"sqlite:///{tmp_path}/personal-relink.db",
        class_delivery_enabled=True,
        auth_mode="development",
        line_channel_access_token="mock-line-token",
    )
    app = create_app(settings)
    sent_to: list[str] = []
    monkeypatch.setattr(
        "scripts.send_pending_line_notifications.push_text_message",
        lambda *, recipient_line_user_id, **_kwargs: sent_to.append(recipient_line_user_id) or "accepted",
    )
    with TestClient(app) as client:
        school_id, classroom_id = _setup(client, "Personal relink test")
        teacher_id = client.get("/api/v1/teachers", params={"school_id": school_id}).json()[0]["id"]
        child_id = _child(client, school_id, classroom_id, "園児", "U-personal-relink")
        record_id = _growth_record(client, school_id, teacher_id, child_id, "承認後に再連携")
        assert client.post(f"/api/v1/records/{record_id}/approve", json={}).status_code == 200
        today = datetime.now(ZoneInfo("Asia/Tokyo")).date().isoformat()
        batch = client.post(
            f"/api/v1/classrooms/{classroom_id}/growth-delivery/propose",
            json={"delivery_date": today},
        ).json()
        approved = client.post(
            f"/api/v1/growth-delivery-batches/{batch['id']}/approve",
            json={"selected_record_ids": [record_id], "teacher_confirmed": True},
        )
        assert approved.status_code == 200, approved.text
        with app.state.session_factory() as db:
            from app.models import Child, School

            db.get(School, school_id).digest_time = "00:00"
            db.get(Child, child_id).guardian_line_linked_at = datetime.now(timezone.utc) + timedelta(days=1)
            db.commit()

        assert send_due_notifications(settings=settings) == (0, 0)
        assert sent_to == []
        notices = client.get("/api/v1/notifications", params={"school_id": school_id}).json()
        assert notices[0]["status"] == "cancelled"


@pytest.mark.parametrize("method,path", [
    ("GET", "/classrooms?school_id=test"),
    ("POST", "/classrooms"),
    ("PATCH", "/classrooms/test"),
    ("PUT", "/children/test/classroom"),
    ("GET", "/class-newsletters?school_id=test"),
    ("POST", "/classrooms/test/class-newsletters"),
    ("PATCH", "/class-newsletters/test"),
    ("POST", "/class-newsletters/test/approve"),
    ("POST", "/class-newsletters/test/cancel"),
    ("POST", "/class-newsletters/test/retry"),
    ("POST", "/classrooms/test/growth-delivery/propose"),
    ("GET", "/growth-delivery-batches/test"),
    ("POST", "/growth-delivery-batches/test/refresh"),
    ("POST", "/growth-delivery-batches/test/approve"),
    ("POST", "/growth-delivery-batches/test/cancel"),
])
def test_class_delivery_defaults_to_paused_and_blocks_all_feature_apis(tmp_path, method, path):
    settings = Settings(database_url=f"sqlite:///{tmp_path}/paused.db", auth_mode="development")
    assert settings.class_delivery_enabled is False
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/v1/auth/config").json()["class_delivery_enabled"] is False
        response = client.request(method, f"/api/v1{path}", json={} if method != "GET" else None)
        assert response.status_code == 404
        assert response.json()["detail"] == "Class delivery is paused"


def _queued_class_work(settings):
    app = create_app(settings)
    with TestClient(app) as client:
        school_id, classroom_id = _setup(client, "Pause resume test")
        teacher_id = client.get("/api/v1/teachers", params={"school_id": school_id}).json()[0]["id"]
        child_id = _child(client, school_id, classroom_id, "テスト園児", "U-local-test")
        _child(client, school_id, classroom_id, "送信済み宛先の園児", "U-history")
        records = [_growth_record(client, school_id, teacher_id, child_id, label)
                   for label in ("選定済み", "未選定")]
        for record_id in records:
            assert client.post(f"/api/v1/records/{record_id}/approve", json={}).status_code == 200
        today = datetime.now(ZoneInfo("Asia/Tokyo")).date().isoformat()
        batch = client.post(f"/api/v1/classrooms/{classroom_id}/growth-delivery/propose",
                            json={"delivery_date": today}).json()
        assert client.post(f"/api/v1/growth-delivery-batches/{batch['id']}/approve", json={
            "selected_record_ids": records[:1], "teacher_confirmed": True,
        }).status_code == 200
        newsletter = client.post(f"/api/v1/classrooms/{classroom_id}/class-newsletters", json={
            "delivery_date": today, "body": "テストのお便りです。",
        }).json()
        assert client.post(f"/api/v1/class-newsletters/{newsletter['id']}/approve",
                           json={"content_checked": True}).status_code == 200
        old_record_id = _growth_record(client, school_id, teacher_id, child_id, "過去の送信済み記録")
        with app.state.session_factory() as db:
            notice = db.scalar(select(Notification).where(Notification.record_id == records[0]))
            notice.status = NotificationStatus.failed
            notice.scheduled_for = datetime.now(timezone.utc) + timedelta(days=60)
            recipient = db.scalar(select(ClassNewsletterRecipient).where(
                ClassNewsletterRecipient.recipient_line_user_id == "U-local-test"
            ))
            recipient.status = "failed"
            sent_recipient = db.scalar(select(ClassNewsletterRecipient).where(
                ClassNewsletterRecipient.recipient_line_user_id == "U-history"
            ))
            sent_recipient.status = "sent"
            sent_recipient.sent_at = datetime.now(timezone.utc)
            db.get(ClassNewsletter, newsletter["id"]).scheduled_for = notice.scheduled_for
            # A historical accepted message contributes to fairness after resumption.
            old_batch = GrowthDeliveryBatch(
                school_id=school_id, classroom_id=classroom_id, delivery_date="2020-01-01",
                daily_limit=1, status="approved", scheduled_for=datetime.now(timezone.utc),
            )
            db.add(old_batch)
            db.flush()
            old_entry = GrowthDeliveryEntry(
                school_id=school_id, classroom_id=classroom_id, batch_id=old_batch.id,
                record_id=old_record_id, child_id=child_id, selected=True,
            )
            db.add(old_entry)
            db.flush()
            db.add(Notification(
                record_id=old_record_id, growth_delivery_entry_id=old_entry.id,
                status=NotificationStatus.sent, sent_at=datetime.now(timezone.utc),
                scheduled_for=datetime.now(timezone.utc), recipient_line_user_id="U-local-test",
            ))
            db.get(Record, old_record_id).status = RecordStatus.dispatched
            db.commit()
    return school_id, classroom_id, teacher_id, child_id, records, batch["id"], newsletter["id"]


def test_pause_resume_preserves_settings_and_history_without_releasing_old_work(tmp_path, monkeypatch):
    from scripts.send_pending_line_notifications import send_due_notifications

    settings = Settings(database_url=f"sqlite:///{tmp_path}/resume.db", auth_mode="development",
                        class_delivery_enabled=True, line_channel_access_token="mock-line-token")
    school_id, classroom_id, teacher_id, child_id, records, batch_id, newsletter_id = _queued_class_work(settings)
    sent = []
    monkeypatch.setattr("scripts.send_pending_line_notifications.push_text_message",
                        lambda **kwargs: sent.append(kwargs["text"]) or "mock-request")
    paused = settings.model_copy(update={"class_delivery_enabled": False})
    paused_app = create_app(paused)
    with TestClient(paused_app) as client:
        assert client.get("/api/v1/readiness").json()["database_migration_current"] is True
        assert client.get("/api/v1/classrooms", params={"school_id": school_id}).status_code == 404
        with paused_app.state.session_factory() as db:
            classroom = db.get(Classroom, classroom_id)
            assert classroom.delivery_enabled is True
            assert classroom.daily_growth_limit == 1
            assert classroom.delivery_enabled_since is None
            assert db.get(Child, child_id).classroom_id == classroom_id
            assert db.get(GrowthDeliveryBatch, batch_id).status == "cancelled"
            assert db.get(ClassNewsletter, newsletter_id).status == "cancelled"
            assert db.scalar(select(Notification).where(Notification.record_id == records[0])).status == NotificationStatus.cancelled
            recipient_states = [row.status for row in db.scalars(select(ClassNewsletterRecipient))]
            assert sorted(recipient_states) == ["cancelled", "sent"]
            assert db.scalar(select(Notification).where(Notification.status == NotificationStatus.sent)) is not None
            assert db.scalar(select(Notification).where(Notification.record_id == records[1])) is None
        legacy_record = _growth_record(client, school_id, teacher_id, child_id, "休止中の成長")
        assert client.post(f"/api/v1/records/{legacy_record}/approve", json={}).status_code == 200
        injury_record = _growth_record(client, school_id, teacher_id, child_id, "休止中のけが")
        with paused_app.state.session_factory() as db:
            db.get(Record, injury_record).category = RecordCategory.injury
            db.commit()
        assert client.post(f"/api/v1/records/{injury_record}/approve", json={}).status_code == 200
        with paused_app.state.session_factory() as db:
            notice = db.scalar(select(Notification).where(Notification.record_id == legacy_record))
            assert notice.growth_delivery_entry_id is None
            notice.scheduled_for = datetime.now(timezone.utc) - timedelta(days=1)
            db.commit()
    resumed_app = create_app(settings)
    with TestClient(resumed_app) as client:
        assert client.get("/api/v1/auth/config").json()["class_delivery_enabled"] is True
        assert client.get("/api/v1/classrooms", params={"school_id": school_id}).json()[0]["delivery_enabled"] is True
        assert send_due_notifications(settings=settings, retry_failed=True) == (2, 0)
        assert len(sent) == 2
        with resumed_app.state.session_factory() as db:
            assert db.get(Classroom, classroom_id).delivery_enabled_since is not None
            assert db.get(GrowthDeliveryBatch, batch_id).status == "cancelled"
            assert db.get(ClassNewsletter, newsletter_id).status == "cancelled"
            assert db.scalar(select(Notification).where(Notification.record_id == legacy_record)).status == NotificationStatus.sent
            assert len(db.scalars(select(Notification).where(Notification.status == NotificationStatus.sent)).all()) == 3
            history_batch = db.scalar(select(GrowthDeliveryBatch).where(
                GrowthDeliveryBatch.delivery_date == "2020-01-01"
            ))
            history_id = history_batch.id
        history = client.get(f"/api/v1/growth-delivery-batches/{history_id}").json()
        assert history["entries"][0]["accepted_delivery_count"] == 1
        later_record = _growth_record(client, school_id, teacher_id, child_id, "再開後の成長")
        assert client.post(f"/api/v1/records/{later_record}/approve", json={}).status_code == 200
        assert not any(row["record_id"] == later_record for row in client.get(
            "/api/v1/notifications", params={"school_id": school_id}
        ).json())


def test_paused_worker_cancels_future_and_failed_work_without_line_credentials(tmp_path, monkeypatch):
    from scripts.send_pending_line_notifications import send_due_notifications

    settings = Settings(database_url=f"sqlite:///{tmp_path}/paused-worker.db", auth_mode="development",
                        class_delivery_enabled=True)
    _, classroom_id, _, _, _, batch_id, newsletter_id = _queued_class_work(settings)
    monkeypatch.setattr("scripts.send_pending_line_notifications.push_text_message",
                        lambda **kwargs: pytest.fail("Pausing must not call LINE"))
    paused = settings.model_copy(update={"class_delivery_enabled": False})
    assert send_due_notifications(settings=paused, dry_run=True) == (0, 0)
    engine = create_app(settings).state.engine
    from app.database import create_session_factory

    with create_session_factory(engine)() as db:
        assert db.get(GrowthDeliveryBatch, batch_id).status == "approved"
    assert send_due_notifications(settings=paused) == (0, 0)
    with create_session_factory(engine)() as db:
        assert db.get(Classroom, classroom_id).delivery_enabled is True
        assert db.get(GrowthDeliveryBatch, batch_id).status == "cancelled"
        assert db.get(ClassNewsletter, newsletter_id).status == "cancelled"
    engine.dispose()


def test_class_assignment_rejects_a_class_from_another_school(tmp_path):
    app = create_app(Settings(database_url=f"sqlite:///{tmp_path}/school-boundary.db", auth_mode="development", class_delivery_enabled=True))
    with TestClient(app) as client:
        first_school_id, first_classroom_id = _setup(client, "Assignment school one")
        child_id = _child(client, first_school_id, first_classroom_id, "園児", None)
        second_school = client.post("/api/v1/schools", json={"name": "Assignment school two"}).json()
        second_class = client.post(
            "/api/v1/classrooms", json={"school_id": second_school["id"], "name": "別園クラス"}
        ).json()
        response = client.put(
            f"/api/v1/children/{child_id}/classroom",
            json={"classroom_id": second_class["id"]},
        )
        assert response.status_code == 422


def test_regular_teacher_can_select_owned_growth_but_cannot_change_class_settings(tmp_path):
    app = create_app(Settings(database_url=f"sqlite:///{tmp_path}/teacher-permissions.db", auth_mode="development", class_delivery_enabled=True))
    with TestClient(app) as client:
        school_id, classroom_id = _setup(client, "Teacher permission test")
        teacher_id = client.get("/api/v1/teachers", params={"school_id": school_id}).json()[0]["id"]
        child_id = _child(client, school_id, classroom_id, "園児", "U-teacher-permission")
        record_id = _growth_record(client, school_id, teacher_id, child_id, "先生本人の成長")
        assert client.post(f"/api/v1/records/{record_id}/approve", json={}).status_code == 200
        with app.state.session_factory() as db:
            teacher = db.get(Teacher, teacher_id)
            teacher.role = TeacherRole.teacher
            db.commit()
            teacher = db.get(Teacher, teacher_id)
        app.dependency_overrides[get_current_teacher] = lambda: CurrentTeacher(
            user=AuthenticatedUser(id="teacher-user", email="teacher@example.test"),
            teacher=teacher,
            is_development=False,
        )

        today = datetime.now(ZoneInfo("Asia/Tokyo")).date().isoformat()
        proposal = client.post(
            f"/api/v1/classrooms/{classroom_id}/growth-delivery/propose",
            json={"delivery_date": today},
        )
        assert proposal.status_code == 200, proposal.text
        approved = client.post(
            f"/api/v1/growth-delivery-batches/{proposal.json()['id']}/approve",
            json={"selected_record_ids": [record_id], "teacher_confirmed": True},
        )
        assert approved.status_code == 200, approved.text
        cannot_change_class = client.patch(
            f"/api/v1/classrooms/{classroom_id}",
            json={"name": "年少", "is_active": True, "delivery_enabled": False, "daily_growth_limit": 1},
        )
        assert cannot_change_class.status_code == 403


def test_teacher_cannot_approve_hidden_candidates_from_other_teachers(tmp_path):
    app = create_app(Settings(database_url=f"sqlite:///{tmp_path}/mixed-teachers.db", auth_mode="development", class_delivery_enabled=True))
    with TestClient(app) as client:
        school_id, classroom_id = _setup(client, "Mixed teacher test")
        teachers = client.get("/api/v1/teachers", params={"school_id": school_id}).json()
        owner_teacher_id = teachers[0]["id"]
        other_teacher = client.post(
            "/api/v1/teachers",
            json={"school_id": school_id, "name": "別の先生", "email": "other@example.test"},
        )
        assert other_teacher.status_code == 201
        other_teacher_id = other_teacher.json()["id"]
        owner_child = _child(client, school_id, classroom_id, "閲覧できる園児", "U-visible")
        other_child = _child(client, school_id, classroom_id, "非表示の園児", "U-hidden")
        owner_record = _growth_record(client, school_id, owner_teacher_id, owner_child, "閲覧できる成長")
        hidden_record = _growth_record(client, school_id, other_teacher_id, other_child, "閲覧できない成長")
        for record_id in (owner_record, hidden_record):
            assert client.post(f"/api/v1/records/{record_id}/approve", json={}).status_code == 200
        configured = client.patch(
            f"/api/v1/classrooms/{classroom_id}",
            json={"name": "年少", "is_active": True, "delivery_enabled": True, "daily_growth_limit": 2},
        )
        assert configured.status_code == 200
        with app.state.session_factory() as db:
            teacher = db.get(Teacher, owner_teacher_id)
            teacher.role = TeacherRole.teacher
            db.commit()
            teacher = db.get(Teacher, owner_teacher_id)
        app.dependency_overrides[get_current_teacher] = lambda: CurrentTeacher(
            user=AuthenticatedUser(id="owner-user", email="owner@example.test"),
            teacher=teacher,
            is_development=False,
        )
        today = datetime.now(ZoneInfo("Asia/Tokyo")).date().isoformat()
        batch_response = client.post(
            f"/api/v1/classrooms/{classroom_id}/growth-delivery/propose",
            json={"delivery_date": today},
        )
        assert batch_response.status_code == 200, batch_response.text
        batch = batch_response.json()
        assert len(batch["entries"]) == 1
        assert batch["entries"][0]["record_id"] == owner_record

        visible_batch = client.get(f"/api/v1/growth-delivery-batches/{batch['id']}")
        assert visible_batch.status_code == 200
        assert visible_batch.json()["requires_admin_review"] is True
        assert [entry["record_id"] for entry in visible_batch.json()["entries"]] == [owner_record]
        hidden_approval = client.post(
            f"/api/v1/growth-delivery-batches/{batch['id']}/approve",
            json={"selected_record_ids": [hidden_record], "teacher_confirmed": True},
        )
        assert hidden_approval.status_code == 403
        owner_approval = client.post(
            f"/api/v1/growth-delivery-batches/{batch['id']}/approve",
            json={"selected_record_ids": [owner_record], "teacher_confirmed": True},
        )
        assert owner_approval.status_code == 200, owner_approval.text
        assert owner_approval.json()["requires_admin_review"] is False
        assert len(client.get("/api/v1/notifications", params={"school_id": school_id}).json()) == 1
        assert client.post(f"/api/v1/growth-delivery-batches/{batch['id']}/cancel").status_code == 200


def test_injury_approval_keeps_its_existing_notification_path_when_class_mode_is_on(tmp_path):
    app = create_app(Settings(database_url=f"sqlite:///{tmp_path}/injury-path.db", auth_mode="development", class_delivery_enabled=True))
    with TestClient(app) as client:
        school_id, classroom_id = _setup(client, "Injury path test")
        teacher_id = client.get("/api/v1/teachers", params={"school_id": school_id}).json()[0]["id"]
        child_id = _child(client, school_id, classroom_id, "園児", "U-injury")
        record_id = _growth_record(client, school_id, teacher_id, child_id, "転んで膝を擦りむいた")
        with app.state.session_factory() as db:
            from app.models import RecordCategory

            db.get(Record, record_id).category = RecordCategory.injury
            db.commit()
        approved = client.post(f"/api/v1/records/{record_id}/approve", json={})
        assert approved.status_code == 200
        notifications = client.get("/api/v1/notifications", params={"school_id": school_id}).json()
        assert len(notifications) == 1
        assert notifications[0]["record_id"] == record_id


def test_trial_class_newsletter_is_never_queued_for_delivery(tmp_path, monkeypatch):
    from scripts.send_pending_line_notifications import send_due_notifications

    settings = Settings(
        database_url=f"sqlite:///{tmp_path}/trial-newsletter.db",
        class_delivery_enabled=True,
        auth_mode="development",
        line_channel_access_token="mock-line-token",
    )
    app = create_app(settings)
    calls: list[str] = []
    monkeypatch.setattr(
        "scripts.send_pending_line_notifications.push_text_message",
        lambda *, recipient_line_user_id, **_kwargs: calls.append(recipient_line_user_id) or "accepted",
    )
    with TestClient(app) as client:
        created = client.post("/api/v1/schools", json={"name": "Trial newsletter test"})
        school_id = created.json()["id"]
        classroom = client.post("/api/v1/classrooms", json={"school_id": school_id, "name": "年少"})
        classroom_id = classroom.json()["id"]
        enabled = client.patch(
            f"/api/v1/classrooms/{classroom_id}",
            json={"name": "年少", "is_active": True, "delivery_enabled": True, "daily_growth_limit": 1},
        )
        assert enabled.status_code == 200
        _child(client, school_id, classroom_id, "試用園児", "U-trial")
        today = datetime.now(ZoneInfo("Asia/Tokyo")).date().isoformat()
        draft = client.post(
            f"/api/v1/classrooms/{classroom_id}/class-newsletters",
            json={"delivery_date": today, "body": "試用中のお便り"},
        ).json()
        approved = client.post(
            f"/api/v1/class-newsletters/{draft['id']}/approve",
            json={"content_checked": True},
        )
        assert approved.status_code == 200
        assert approved.json()["is_trial"] is True
        assert send_due_notifications(settings=settings) == (0, 0)
        assert calls == []


def test_legacy_delivery_stays_enabled_for_classes_that_have_not_opted_in(tmp_path):
    app = create_app(Settings(database_url=f"sqlite:///{tmp_path}/legacy-mode.db", auth_mode="development", class_delivery_enabled=True))
    with TestClient(app) as client:
        school_response = client.post("/api/v1/schools", json={"name": "Legacy delivery test"})
        school_id = school_response.json()["id"]
        client.patch(
            f"/api/v1/schools/{school_id}/trial-mode",
            json={"trial_mode": False, "delivery_confirmed": True},
        )
        teacher_id = client.post(
            "/api/v1/teachers",
            json={"school_id": school_id, "name": "先生", "email": "legacy@example.com"},
        ).json()["id"]
        classroom_id = client.post(
            "/api/v1/classrooms", json={"school_id": school_id, "name": "年少"}
        ).json()["id"]
        child_id = _child(client, school_id, classroom_id, "既存園児", "U-legacy")
        record_id = _growth_record(client, school_id, teacher_id, child_id, "既存方式の成長")
        assert client.post(f"/api/v1/records/{record_id}/approve", json={}).status_code == 200
        notifications = client.get("/api/v1/notifications", params={"school_id": school_id}).json()
        assert len(notifications) == 1
        assert notifications[0]["record_id"] == record_id


def test_class_newsletter_deduplicates_guardians_and_retries_only_failed_recipients(tmp_path, monkeypatch):
    from scripts.send_pending_line_notifications import send_due_notifications

    settings = Settings(
        database_url=f"sqlite:///{tmp_path}/newsletter.db",
        class_delivery_enabled=True,
        auth_mode="development",
        line_channel_access_token="mock-line-token",
    )
    app = create_app(settings)
    calls: list[str] = []
    failed_once: set[str] = set()

    def fake_push_text_message(*, recipient_line_user_id: str, **_kwargs) -> str:
        calls.append(recipient_line_user_id)
        if recipient_line_user_id == "U-second" and recipient_line_user_id not in failed_once:
            failed_once.add(recipient_line_user_id)
            raise httpx.ConnectError("mock transport failure")
        return f"accepted-{len(calls)}"

    monkeypatch.setattr("scripts.send_pending_line_notifications.push_text_message", fake_push_text_message)

    with TestClient(app) as client:
        school_id, classroom_id = _setup(client, "Newsletter test")
        with app.state.session_factory() as db:
            from app.models import School

            school = db.get(School, school_id)
            school.digest_time = "00:00"
            db.commit()
        _child(client, school_id, classroom_id, "園児A", "U-shared")
        _child(client, school_id, classroom_id, "園児B", "U-shared")
        _child(client, school_id, classroom_id, "園児C", "U-second")
        today = datetime.now(ZoneInfo("Asia/Tokyo")).date().isoformat()
        draft = client.post(
            f"/api/v1/classrooms/{classroom_id}/class-newsletters",
            json={"delivery_date": today, "body": "今日はみんなで外遊びをしました。"},
        )
        assert draft.status_code == 201, draft.text
        approved = client.post(
            f"/api/v1/class-newsletters/{draft.json()['id']}/approve",
            json={"content_checked": True},
        )
        assert approved.status_code == 200, approved.text
        assert approved.json()["recipient_count"] == 2

        sent, failed = send_due_notifications(settings=settings)
        assert (sent, failed) == (1, 1)
        assert sorted(calls) == ["U-second", "U-shared"]

        retry = client.post(f"/api/v1/class-newsletters/{draft.json()['id']}/retry")
        assert retry.status_code == 200
        sent, failed = send_due_notifications(retry_failed=True, settings=settings)
        assert (sent, failed) == (1, 0)
        assert calls.count("U-shared") == 1
        assert calls.count("U-second") == 2

        with app.state.session_factory() as db:
            rows = list(db.scalars(select(ClassNewsletterRecipient)))
            assert {row.status for row in rows} == {"sent"}


def test_approved_newsletter_is_not_sent_to_a_newly_linked_guardian(tmp_path, monkeypatch):
    from scripts.send_pending_line_notifications import send_due_notifications

    settings = Settings(
        database_url=f"sqlite:///{tmp_path}/late-guardian.db",
        class_delivery_enabled=True,
        auth_mode="development",
        line_channel_access_token="mock-line-token",
    )
    app = create_app(settings)
    sent_to: list[str] = []
    monkeypatch.setattr(
        "scripts.send_pending_line_notifications.push_text_message",
        lambda *, recipient_line_user_id, **_kwargs: sent_to.append(recipient_line_user_id) or "ok",
    )
    with TestClient(app) as client:
        school_id, classroom_id = _setup(client, "Late guardian test")
        child_id = _child(client, school_id, classroom_id, "園児", "U-relinked")
        today = datetime.now(ZoneInfo("Asia/Tokyo")).date().isoformat()
        draft = client.post(
            f"/api/v1/classrooms/{classroom_id}/class-newsletters",
            json={"delivery_date": today, "body": "クラスのお知らせです。"},
        ).json()
        approved = client.post(
            f"/api/v1/class-newsletters/{draft['id']}/approve",
            json={"content_checked": True},
        )
        assert approved.status_code == 200
        with app.state.session_factory() as db:
            from app.models import Child, School

            school = db.get(School, school_id)
            child = db.get(Child, child_id)
            child.guardian_line_linked_at = datetime.now(timezone.utc) + timedelta(days=1)
            db.commit()
        assert send_due_notifications(settings=settings) == (0, 0)
        assert sent_to == []
