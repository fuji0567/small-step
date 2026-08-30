"""Print the secret-free readiness summary exposed by a running Small Step API."""

from __future__ import annotations

import json
import sys

import httpx

from app.config import Settings


def main() -> None:
    settings = Settings()
    endpoint = f"{settings.edge_api_url.rstrip('/')}/api/v1/readiness"
    try:
        response = httpx.get(endpoint, timeout=settings.edge_api_timeout_seconds)
        payload = response.json()
    except (httpx.HTTPError, ValueError):
        raise SystemExit("稼働状態を確認できませんでした。APIの起動と EDGE_API_URL を確認してください。")

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if response.status_code != 200 or payload.get("status") != "ready":
        raise SystemExit("このAPIはまだ準備完了ではありません。録音端末の送信先は切り替えないでください。")


if __name__ == "__main__":
    main()
