from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


USERS = {
    "admin-a-token": {
        "id": "00000000-0000-0000-0000-000000000001",
        "email": "admin-a@example.com",
    },
    "teacher-a-token": {
        "id": "00000000-0000-0000-0000-000000000002",
        "email": "teacher-a@example.com",
    },
    "teacher-b-token": {
        "id": "00000000-0000-0000-0000-000000000003",
        "email": "teacher-b@example.com",
    },
    "admin-b-token": {
        "id": "00000000-0000-0000-0000-000000000004",
        "email": "admin-b@example.com",
    },
}


class FakeSupabaseResponse:
    status_code = 200

    def __init__(self, payload: dict[str, str]):
        self._payload = payload

    def json(self) -> dict[str, str]:
        return self._payload


@pytest.fixture
def record_detail_context(tmp_path, monkeypatch):
    def fake_get(_url, headers, timeout):
        token = headers["Authorization"].removeprefix("Bearer ")
        return FakeSupabaseResponse(USERS[token])

    monkeypatch.setattr("app.api.dependencies.httpx.get", fake_get)
    app = create_app(
        Settings(
            database_url=f"sqlite:///{tmp_path}/test.db",
            auth_mode="supabase",
            supabase_url="https://example.supabase.co",
            supabase_publishable_key="sb_publishable_test",
            supabase_bootstrap_admin_emails="admin-a@example.com,admin-b@example.com",
        )
    )

    headers = {
        name: {"Authorization": f"Bearer {token}"}
        for name, token in {
            "admin_a": "admin-a-token",
            "teacher_a": "teacher-a-token",
            "teacher_b": "teacher-b-token",
            "admin_b": "admin-b-token",
        }.items()
    }

    with TestClient(app) as client:
        school_a_response = client.post(
            "/api/v1/schools",
            headers=headers["admin_a"],
            json={"name": "単体取得A園", "initial_admin_name": "A園管理者"},
        )
        assert school_a_response.status_code == 201
        school_a_id = school_a_response.json()["id"]

        teachers = {}
        admin_a = client.get("/api/v1/auth/me", headers=headers["admin_a"])
        assert admin_a.status_code == 200
        teachers["admin_a"] = admin_a.json()
        for name, email in (
            ("teacher_a", "teacher-a@example.com"),
            ("teacher_b", "teacher-b@example.com"),
        ):
            response = client.post(
                "/api/v1/teachers",
                headers=headers["admin_a"],
                json={"school_id": school_a_id, "name": name, "email": email},
            )
            assert response.status_code == 201
            linked = client.post("/api/v1/auth/link-teacher", headers=headers[name])
            assert linked.status_code == 200
            teachers[name] = linked.json()

        school_b_response = client.post(
            "/api/v1/schools",
            headers=headers["admin_b"],
            json={"name": "単体取得B園", "initial_admin_name": "B園管理者"},
        )
        assert school_b_response.status_code == 201
        school_b_id = school_b_response.json()["id"]
        admin_b = client.get("/api/v1/auth/me", headers=headers["admin_b"])
        assert admin_b.status_code == 200
        teachers["admin_b"] = admin_b.json()

        child_response = client.post(
            "/api/v1/children",
            headers=headers["admin_a"],
            json={
                "school_id": school_a_id,
                "display_name": "単体取得園児",
                "guardian_line_user_id": "guardian-line-secret-value",
            },
        )
        assert child_response.status_code == 201

        def create_record(
            *, school_id: str, teacher_id: str, token_headers: dict[str, str], suffix: str
        ) -> dict:
            response = client.post(
                "/api/v1/records",
                headers=token_headers,
                json={
                    "school_id": school_id,
                    "teacher_id": teacher_id,
                    "child_id": child_response.json()["id"] if school_id == school_a_id else None,
                    "category": "injury",
                    "source_event_id": f"record-detail-{suffix}",
                    "confidence": 0.9,
                    "occurred_at": datetime.now(timezone.utc).isoformat(),
                    "summary": f"単体取得テスト {suffix}",
                    "conversation_prompt": "今日の出来事を聞いてみてください。",
                    "anonymized_context": "話者Aが安全に加工済みの内容を話しました。",
                },
            )
            assert response.status_code == 201
            return response.json()

        pending = create_record(
            school_id=school_a_id,
            teacher_id=teachers["teacher_a"]["id"],
            token_headers=headers["admin_a"],
            suffix="pending",
        )
        approved = create_record(
            school_id=school_a_id,
            teacher_id=teachers["teacher_a"]["id"],
            token_headers=headers["admin_a"],
            suffix="approved",
        )
        rejected = create_record(
            school_id=school_a_id,
            teacher_id=teachers["teacher_a"]["id"],
            token_headers=headers["admin_a"],
            suffix="rejected",
        )
        other_teacher = create_record(
            school_id=school_a_id,
            teacher_id=teachers["teacher_b"]["id"],
            token_headers=headers["admin_a"],
            suffix="other-teacher",
        )
        other_school = create_record(
            school_id=school_b_id,
            teacher_id=teachers["admin_b"]["id"],
            token_headers=headers["admin_b"],
            suffix="other-school",
        )

        approve_response = client.post(
            f"/api/v1/records/{approved['id']}/approve",
            headers=headers["admin_a"],
            json={},
        )
        assert approve_response.status_code == 200
        reject_response = client.post(
            f"/api/v1/records/{rejected['id']}/reject",
            headers=headers["admin_a"],
        )
        assert reject_response.status_code == 200

        yield {
            "client": client,
            "headers": headers,
            "school_a_id": school_a_id,
            "teachers": teachers,
            "records": {
                "pending": pending,
                "approved": approved,
                "rejected": rejected,
                "other_teacher": other_teacher,
                "other_school": other_school,
            },
        }


def test_record_detail_requires_authentication_and_enforces_record_scope(record_detail_context):
    client = record_detail_context["client"]
    headers = record_detail_context["headers"]
    records = record_detail_context["records"]

    assert client.get(f"/api/v1/records/{records['pending']['id']}").status_code == 401
    assert client.get(
        f"/api/v1/records/{records['other_teacher']['id']}", headers=headers["admin_a"]
    ).status_code == 200
    assert client.get(
        f"/api/v1/records/{records['pending']['id']}", headers=headers["teacher_a"]
    ).status_code == 200
    assert client.get(
        f"/api/v1/records/{records['other_teacher']['id']}", headers=headers["teacher_a"]
    ).status_code == 403
    assert client.get(
        f"/api/v1/records/{records['pending']['id']}", headers=headers["admin_b"]
    ).status_code == 403
    assert client.get(
        "/api/v1/records/00000000-0000-0000-0000-000000000099",
        headers=headers["admin_a"],
    ).status_code == 404


def test_record_detail_returns_each_status_without_secrets_and_keeps_export_route(record_detail_context):
    client = record_detail_context["client"]
    headers = record_detail_context["headers"]
    records = record_detail_context["records"]

    expected_fields = {
        "id",
        "school_id",
        "teacher_id",
        "child_id",
        "category",
        "status",
        "source_event_id",
        "confidence",
        "audio_processing_incomplete",
        "occurred_at",
        "summary",
        "conversation_prompt",
        "anonymized_context",
        "reviewed_at",
        "created_at",
        "updated_at",
    }
    for expected_status in ("pending", "approved", "rejected"):
        response = client.get(
            f"/api/v1/records/{records[expected_status]['id']}",
            headers=headers["teacher_a"],
        )
        assert response.status_code == 200
        body = response.json()
        assert body["id"] == records[expected_status]["id"]
        assert body["status"] == ("pending_review" if expected_status == "pending" else expected_status)
        assert set(body) == expected_fields
        assert "guardian-line-secret-value" not in response.text
        assert {
            "guardian_line_user_id",
            "recipient_line_user_id",
            "api_key",
            "api_key_hash",
            "token",
            "token_hash",
            "raw_audio_path",
            "filename",
            "transcript",
        }.isdisjoint(body)

    export_response = client.get(
        "/api/v1/records/export.csv",
        headers=headers["admin_a"],
        params={"school_id": record_detail_context["school_a_id"]},
    )
    assert export_response.status_code == 200
    assert export_response.headers["content-type"].startswith("text/csv")


def test_record_reassignment_is_admin_only_school_scoped_and_changes_teacher_access(record_detail_context):
    client = record_detail_context["client"]
    headers = record_detail_context["headers"]
    records = record_detail_context["records"]
    teachers = record_detail_context["teachers"]
    pending_id = records["pending"]["id"]

    unauthenticated = client.patch(
        f"/api/v1/records/{pending_id}/assignee",
        json={"teacher_id": teachers["teacher_b"]["id"]},
    )
    assert unauthenticated.status_code == 401

    regular_teacher = client.patch(
        f"/api/v1/records/{pending_id}/assignee",
        headers=headers["teacher_a"],
        json={"teacher_id": teachers["teacher_b"]["id"]},
    )
    assert regular_teacher.status_code == 403

    cross_school = client.patch(
        f"/api/v1/records/{pending_id}/assignee",
        headers=headers["admin_a"],
        json={"teacher_id": teachers["admin_b"]["id"]},
    )
    assert cross_school.status_code == 422

    same_teacher = client.patch(
        f"/api/v1/records/{pending_id}/assignee",
        headers=headers["admin_a"],
        json={"teacher_id": teachers["teacher_a"]["id"]},
    )
    assert same_teacher.status_code == 409

    inactive = client.post(
        "/api/v1/teachers",
        headers=headers["admin_a"],
        json={
            "school_id": record_detail_context["school_a_id"],
            "name": "利用停止先生",
            "email": "inactive@example.com",
        },
    )
    assert inactive.status_code == 201
    disabled = client.post(
        f"/api/v1/teachers/{inactive.json()['id']}/disable",
        headers=headers["admin_a"],
    )
    assert disabled.status_code == 200
    inactive_target = client.patch(
        f"/api/v1/records/{pending_id}/assignee",
        headers=headers["admin_a"],
        json={"teacher_id": inactive.json()["id"]},
    )
    assert inactive_target.status_code == 409

    processed = client.patch(
        f"/api/v1/records/{records['approved']['id']}/assignee",
        headers=headers["admin_a"],
        json={"teacher_id": teachers["teacher_b"]["id"]},
    )
    assert processed.status_code == 409

    reassigned = client.patch(
        f"/api/v1/records/{pending_id}/assignee",
        headers=headers["admin_a"],
        json={"teacher_id": teachers["teacher_b"]["id"]},
    )
    assert reassigned.status_code == 200
    assert reassigned.json()["teacher_id"] == teachers["teacher_b"]["id"]

    assert client.get(
        f"/api/v1/records/{pending_id}", headers=headers["teacher_a"]
    ).status_code == 403
    assert client.get(
        f"/api/v1/records/{pending_id}", headers=headers["teacher_b"]
    ).status_code == 200
    old_assignee_records = client.get(
        "/api/v1/records",
        headers=headers["teacher_a"],
        params={
            "school_id": record_detail_context["school_a_id"],
            "record_status": "pending_review",
        },
    )
    assert old_assignee_records.status_code == 200
    assert old_assignee_records.json() == []
    new_assignee_records = client.get(
        "/api/v1/records",
        headers=headers["teacher_b"],
        params={
            "school_id": record_detail_context["school_a_id"],
            "record_status": "pending_review",
        },
    )
    assert new_assignee_records.status_code == 200
    assert {record["id"] for record in new_assignee_records.json()} == {
        pending_id,
        records["other_teacher"]["id"],
    }

    audit_events = client.get(
        "/api/v1/audit-events",
        headers=headers["admin_a"],
        params={
            "school_id": record_detail_context["school_a_id"],
            "action": "record_reassigned",
        },
    )
    assert audit_events.status_code == 200
    assert audit_events.json() == [
        {
            "action": "record_reassigned",
            "target_type": "record",
            "actor_display_name": "A園管理者",
            "created_at": audit_events.json()[0]["created_at"],
        }
    ]
