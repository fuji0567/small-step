"""Register an edge device as the signed-in school administrator.

The generated key is deliberately printed once so it can be copied into the
device's secure configuration. Never paste that key into chat or source code.
"""

from __future__ import annotations

import getpass
import sys

import httpx
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def main() -> None:
    settings = Settings()
    if settings.auth_mode != "supabase" or not settings.supabase_url or not settings.supabase_publishable_key:
        raise SystemExit(".env のSupabase Auth設定を確認してください。")

    email = input("Supabase login email: ").strip()
    password = getpass.getpass("Supabase login password（画面には表示されません）: ")
    device_name = input("Device name（例: 胸元マイク 01）: ").strip()
    if not email or not password or not device_name:
        raise SystemExit("メールアドレス、パスワード、端末名をすべて入力してください。")

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
        profile_response = client.get("/api/v1/auth/me", headers=headers)
        if profile_response.status_code != 200:
            raise SystemExit("バックエンドで管理者認証を確認できませんでした。")
        profile = profile_response.json()
        response = client.post(
            "/api/v1/edge-devices",
            headers=headers,
            json={
                "school_id": profile["school_id"],
                "teacher_id": profile["id"],
                "name": device_name,
            },
        )
    if response.status_code == 409:
        raise SystemExit("同じ端末名が登録済みです。別の端末名を使うか、後でキーを再発行してください。")
    if response.status_code != 201:
        raise SystemExit(f"端末登録に失敗しました（HTTP {response.status_code}）。")

    device = response.json()
    print("端末を登録しました。次のAPIキーは今回だけ表示されます。")
    print(device["api_key"])
    print("このキーは端末の安全な設定領域へ保存し、チャット・Git・ソースコードには貼り付けないでください。")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n中止しました。設定は変更していません。", file=sys.stderr)
        raise SystemExit(130)
