from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_growth_record_is_reviewed_and_scheduled(tmp_path):
    app = create_app(Settings(database_url=f"sqlite:///{tmp_path}/test.db", auth_mode="development"))
    with TestClient(app) as client:
        school = client.post("/api/v1/schools", json={"name": "ひまわり幼稚園"})
        assert school.status_code == 201
        school_id = school.json()["id"]

        teacher = client.post(
            "/api/v1/teachers",
            json={"school_id": school_id, "name": "山田先生", "email": "yamada@example.com"},
        )
        assert teacher.status_code == 201

        child = client.post(
            "/api/v1/children",
            json={
                "school_id": school_id,
                "display_name": "さくら",
                "guardian_line_user_id": "U-demo-parent",
            },
        )
        assert child.status_code == 201

        record = client.post(
            "/api/v1/records",
            json={
                "school_id": school_id,
                "teacher_id": teacher.json()["id"],
                "child_id": child.json()["id"],
                "category": "growth",
                "source_event_id": "edge-001",
                "confidence": 0.95,
                "occurred_at": datetime.now(timezone.utc).isoformat(),
                "summary": "鉄棒に初めて挑戦しました。",
                "conversation_prompt": "今日は鉄棒に挑戦したそうです。",
                "anonymized_context": "園児が運動遊びに挑戦した会話。",
            },
        )
        assert record.status_code == 201
        assert record.json()["status"] == "pending_review"

        approved = client.post(f"/api/v1/records/{record.json()['id']}/approve", json={})
        assert approved.status_code == 200
        assert approved.json()["status"] == "approved"

        ready = client.get(
            "/api/v1/notifications/ready",
            params={"now": (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()},
        )
        assert ready.status_code == 200
        assert len(ready.json()) == 1


def test_injury_is_immediately_queued_after_approval(tmp_path):
    app = create_app(Settings(database_url=f"sqlite:///{tmp_path}/test.db", auth_mode="development"))
    with TestClient(app) as client:
        school_id = client.post("/api/v1/schools", json={"name": "あおぞら幼稚園"}).json()["id"]
        teacher_id = client.post(
            "/api/v1/teachers",
            json={"school_id": school_id, "name": "佐藤先生", "email": "sato@example.com"},
        ).json()["id"]
        record = client.post(
            "/api/v1/records",
            json={
                "school_id": school_id,
                "teacher_id": teacher_id,
                "category": "injury",
                "confidence": 0.88,
                "occurred_at": datetime.now(timezone.utc).isoformat(),
                "summary": "転倒してひざを擦りむきました。",
            },
        ).json()
        client.post(f"/api/v1/records/{record['id']}/approve", json={})
        ready = client.get("/api/v1/notifications/ready")
        assert len(ready.json()) == 1
        sent = client.post(
            f"/api/v1/notifications/{ready.json()[0]['id']}/mark-sent",
            json={"provider_message_id": "line-message-001"},
        )
        assert sent.status_code == 200
        assert sent.json()["status"] == "sent"


def test_supabase_user_links_to_pre_registered_teacher(tmp_path, monkeypatch):
    users = {
        "admin-token": {"id": "00000000-0000-0000-0000-000000000001", "email": "admin@example.com"},
        "teacher-token": {"id": "00000000-0000-0000-0000-000000000002", "email": "teacher@example.com"},
    }

    class FakeResponse:
        status_code = 200

        def __init__(self, payload):
            self.payload = payload

        def json(self):
            return self.payload

    def fake_get(_url, headers, timeout):
        token = headers["Authorization"].removeprefix("Bearer ")
        return FakeResponse(users[token])

    monkeypatch.setattr("app.api.dependencies.httpx.get", fake_get)
    app = create_app(
        Settings(
            database_url=f"sqlite:///{tmp_path}/test.db",
            auth_mode="supabase",
            supabase_url="https://example.supabase.co",
            supabase_publishable_key="sb_publishable_test",
            supabase_bootstrap_admin_emails="admin@example.com",
        )
    )
    with TestClient(app) as client:
        admin_headers = {"Authorization": "Bearer admin-token"}
        school = client.post(
            "/api/v1/schools",
            headers=admin_headers,
            json={"name": "認証テスト園", "initial_admin_name": "管理者先生"},
        )
        assert school.status_code == 201
        school_id = school.json()["id"]
        assert client.get("/api/v1/auth/me", headers=admin_headers).json()["role"] == "school_admin"

        teacher = client.post(
            "/api/v1/teachers",
            headers=admin_headers,
            json={"school_id": school_id, "name": "担当先生", "email": "teacher@example.com"},
        )
        assert teacher.status_code == 201

        linked = client.post("/api/v1/auth/link-teacher", headers={"Authorization": "Bearer teacher-token"})
        assert linked.status_code == 200
        assert linked.json()["email"] == "teacher@example.com"


def test_edge_device_key_can_only_submit_anonymized_records(tmp_path):
    app = create_app(Settings(database_url=f"sqlite:///{tmp_path}/test.db", auth_mode="development"))
    with TestClient(app) as client:
        school_id = client.post("/api/v1/schools", json={"name": "端末認証テスト園"}).json()["id"]
        teacher_id = client.post(
            "/api/v1/teachers",
            json={"school_id": school_id, "name": "端末担当先生", "email": "edge-teacher@example.com"},
        ).json()["id"]
        device = client.post(
            "/api/v1/edge-devices",
            json={"school_id": school_id, "teacher_id": teacher_id, "name": "胸元マイク 01"},
        )
        assert device.status_code == 201
        first_key = device.json()["api_key"]
        assert first_key.startswith("otayori_edge_")
        assert client.get("/api/v1/edge/me", headers={"X-Edge-Api-Key": first_key}).status_code == 200

        devices = client.get("/api/v1/edge-devices", params={"school_id": school_id})
        assert devices.status_code == 200
        assert "api_key" not in devices.json()[0]

        record_payload = {
            "category": "growth",
            "source_event_id": "device-test-001",
            "confidence": 0.91,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "summary": "片付けに取り組みました。",
        }
        headers = {"X-Edge-Api-Key": first_key}
        raw_audio_attempt = client.post(
            "/api/v1/edge/records",
            headers=headers,
            json={**record_payload, "raw_audio": "must-not-be-accepted"},
        )
        assert raw_audio_attempt.status_code == 422

        record = client.post("/api/v1/edge/records", headers=headers, json=record_payload)
        assert record.status_code == 201
        assert record.json()["teacher_id"] == teacher_id
        assert record.json()["status"] == "pending_review"

        rotated = client.post(f"/api/v1/edge-devices/{device.json()['id']}/rotate-key")
        assert rotated.status_code == 200
        second_key = rotated.json()["api_key"]
        assert second_key != first_key
        assert client.post(
            "/api/v1/edge/records",
            headers={"X-Edge-Api-Key": first_key},
            json={**record_payload, "source_event_id": "device-test-002"},
        ).status_code == 401

        assert client.post(
            "/api/v1/edge/records",
            headers={"X-Edge-Api-Key": second_key},
            json={**record_payload, "source_event_id": "device-test-002"},
        ).status_code == 201

        assert client.post(f"/api/v1/edge-devices/{device.json()['id']}/disable").status_code == 200
        assert client.post(
            "/api/v1/edge/records",
            headers={"X-Edge-Api-Key": second_key},
            json={**record_payload, "source_event_id": "device-test-003"},
        ).status_code == 401
