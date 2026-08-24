"""Approve the newest pending candidate created by send_demo_from_edge.py."""

from __future__ import annotations

import getpass
import sys

import httpx
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


TEST_CHILD_NAME = "【テスト】さくら"
EDGE_TEST_PREFIX = "【端末テスト】"


def main() -> None:
    settings = Settings()
    if settings.auth_mode != "supabase" or not settings.supabase_url or not settings.supabase_publishable_key:
        raise SystemExit(".env のSupabase Auth設定を確認してください。")

    email = input("Supabase login email: ").strip()
    password = getpass.getpass("Supabase login password（画面には表示されません）: ")
    if not email or not password:
        raise SystemExit("メールアドレスとパスワードを入力してください。")
    try:
        token_response = httpx.post(
            f"{settings.supabase_url.rstrip('/')}/auth/v1/token?grant_type=password",
            headers={"apikey": settings.supabase_publishable_key},
            json={"email": email, "password": password},
            timeout=15,
        )
    except httpx.HTTPError as exc:
        raise SystemExit(f"Supabaseへ接続できませんでした: {exc}") from exc
    access_token = token_response.json().get("access_token") if token_response.status_code == 200 else None
    if not access_token:
        raise SystemExit("ログインに失敗しました。メールアドレスとパスワードを確認してください。")

    headers = {"Authorization": f"Bearer {access_token}"}
    with TestClient(create_app(settings)) as client:
        profile = client.get("/api/v1/auth/me", headers=headers)
        if profile.status_code != 200:
            raise SystemExit("バックエンドで管理者認証を確認できませんでした。")
        school_id = profile.json()["school_id"]
        records_response = client.get(
            "/api/v1/records",
            params={"school_id": school_id, "record_status": "pending_review"},
            headers=headers,
        )
        if records_response.status_code != 200:
            raise SystemExit("承認待ち記録を取得できませんでした。")
        record = next(
            (item for item in records_response.json() if item["summary"].startswith(EDGE_TEST_PREFIX)),
            None,
        )
        if record is None:
            raise SystemExit("承認待ちの端末テスト記録が見つかりません。先に send_demo_from_edge.py を実行してください。")

        children_response = client.get("/api/v1/children", params={"school_id": school_id}, headers=headers)
        if children_response.status_code != 200:
            raise SystemExit("園児一覧を取得できませんでした。")
        child = next((item for item in children_response.json() if item["display_name"] == TEST_CHILD_NAME), None)
        approval_payload = {"child_id": child["id"]} if child else {}
        approval_response = client.post(
            f"/api/v1/records/{record['id']}/approve",
            headers=headers,
            json=approval_payload,
        )
        if approval_response.status_code != 200:
            raise SystemExit(f"記録を承認できませんでした（HTTP {approval_response.status_code}）。")

        notification_response = client.get(
            "/api/v1/notifications/ready",
            params={"now": "2099-01-01T00:00:00Z"},
            headers=headers,
        )
        if notification_response.status_code != 200 or not any(
            item["record_id"] == record["id"] for item in notification_response.json()
        ):
            raise SystemExit("承認はできましたが、通知待ちを確認できませんでした。")

    print("端末テスト記録を管理者として承認し、通知待ちを確認しました。")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n中止しました。", file=sys.stderr)
        raise SystemExit(130)
