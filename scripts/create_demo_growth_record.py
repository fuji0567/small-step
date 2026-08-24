"""Create one clearly-labelled test child and approved growth record.

This exercises the real Supabase-authenticated API without printing a password
or access token. Re-running the script reuses the same test data.
"""

from __future__ import annotations

from datetime import datetime, timezone
import getpass
import sys

import httpx
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


TEST_CHILD_NAME = "【テスト】さくら"
TEST_SOURCE_EVENT_ID = "demo-growth-record-v1"


def require_success(response, action: str) -> dict | list:
    if 200 <= response.status_code < 300:
        return response.json()
    raise SystemExit(f"{action} に失敗しました（HTTP {response.status_code}）。")


def obtain_access_token(settings: Settings) -> str:
    email = input("Supabase login email: ").strip()
    password = getpass.getpass("Supabase login password（画面には表示されません）: ")
    if not email or not password:
        raise SystemExit("メールアドレスとパスワードを入力してください。")
    try:
        response = httpx.post(
            f"{settings.supabase_url.rstrip('/')}/auth/v1/token?grant_type=password",
            headers={"apikey": settings.supabase_publishable_key},
            json={"email": email, "password": password},
            timeout=15,
        )
    except httpx.HTTPError as exc:
        raise SystemExit(f"Supabaseへ接続できませんでした: {exc}") from exc
    if response.status_code != 200 or not response.json().get("access_token"):
        raise SystemExit("ログインに失敗しました。メールアドレスとパスワードを確認してください。")
    return response.json()["access_token"]


def main() -> None:
    settings = Settings()
    if settings.auth_mode != "supabase" or not settings.supabase_url or not settings.supabase_publishable_key:
        raise SystemExit(".env のSupabase Auth設定を確認してください。")

    access_token = obtain_access_token(settings)
    headers = {"Authorization": f"Bearer {access_token}"}

    with TestClient(create_app(settings)) as client:
        profile = require_success(client.get("/api/v1/auth/me", headers=headers), "管理者認証")
        school_id = profile["school_id"]
        teacher_id = profile["id"]

        children = require_success(
            client.get("/api/v1/children", params={"school_id": school_id}, headers=headers),
            "園児一覧の取得",
        )
        child = next((item for item in children if item["display_name"] == TEST_CHILD_NAME), None)
        if child is None:
            child = require_success(
                client.post(
                    "/api/v1/children",
                    headers=headers,
                    json={"school_id": school_id, "display_name": TEST_CHILD_NAME},
                ),
                "テスト園児の作成",
            )

        records = require_success(
            client.get("/api/v1/records", params={"school_id": school_id}, headers=headers),
            "記録一覧の取得",
        )
        record = next((item for item in records if item["source_event_id"] == TEST_SOURCE_EVENT_ID), None)
        if record is None:
            record = require_success(
                client.post(
                    "/api/v1/records",
                    headers=headers,
                    json={
                        "school_id": school_id,
                        "teacher_id": teacher_id,
                        "child_id": child["id"],
                        "category": "growth",
                        "source_event_id": TEST_SOURCE_EVENT_ID,
                        "confidence": 0.95,
                        "occurred_at": datetime.now(timezone.utc).isoformat(),
                        "summary": "テスト記録：友だちと協力して片付けに取り組みました。",
                        "conversation_prompt": "お片付けでは、どんなことを頑張ったのかな？",
                        "anonymized_context": "園内活動のテスト用要約です。",
                    },
                ),
                "成長記録候補の作成",
            )

        if record["status"] == "pending_review":
            record = require_success(
                client.post(f"/api/v1/records/{record['id']}/approve", headers=headers, json={}),
                "記録の承認",
            )
        if record["status"] != "approved":
            raise SystemExit("テスト記録は承認待ちまたは承認済みではありません。変更していません。")

        ready_notifications = require_success(
            client.get(
                "/api/v1/notifications/ready",
                params={"now": "2099-01-01T00:00:00Z"},
                headers=headers,
            ),
            "通知待ち一覧の取得",
        )
        if not any(item["record_id"] == record["id"] for item in ready_notifications):
            raise SystemExit("記録は承認されましたが、通知待ちの作成を確認できませんでした。")

    print("テスト園児・成長記録・承認後の通知待ちを確認しました。")
    print("テストデータ名: 【テスト】さくら")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n中止しました。", file=sys.stderr)
        raise SystemExit(130)
