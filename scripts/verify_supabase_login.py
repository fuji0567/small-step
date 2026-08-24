"""Verify a real Supabase login can access the Otayori AI backend.

The password is hidden and access tokens are never printed or stored.
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
    if settings.auth_mode != "supabase":
        raise SystemExit("AUTH_MODE=supabase を .env に設定してください。")
    if not settings.supabase_url or not settings.supabase_publishable_key:
        raise SystemExit("SUPABASE_URL と SUPABASE_PUBLISHABLE_KEY を .env に設定してください。")

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

    if token_response.status_code != 200:
        raise SystemExit("ログインに失敗しました。メールアドレスとパスワードを確認してください。")
    access_token = token_response.json().get("access_token")
    if not access_token:
        raise SystemExit("Supabaseからアクセストークンを取得できませんでした。")

    with TestClient(create_app(settings)) as client:
        backend_response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )

    if backend_response.status_code != 200:
        raise SystemExit(
            "ログインはできましたが、バックエンドの利用者登録を確認できませんでした。"
            f"（HTTP {backend_response.status_code}）"
        )

    profile = backend_response.json()
    if profile.get("role") != "school_admin":
        raise SystemExit("ログインはできましたが、この利用者は園の管理者として登録されていません。")
    print("Supabaseログインとバックエンドの管理者認証を確認しました。")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n中止しました。設定は変更していません。", file=sys.stderr)
        raise SystemExit(130)
