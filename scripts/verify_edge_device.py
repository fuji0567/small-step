"""Verify an edge-device API key without printing it or writing any record."""

from __future__ import annotations

import getpass

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def main() -> None:
    settings = Settings()
    api_key = settings.edge_api_key or getpass.getpass("Edge device API key（画面には表示されません）: ")
    if not api_key:
        raise SystemExit(".env に EDGE_API_KEY を設定するか、APIキーを入力してください。")

    with TestClient(create_app(settings)) as client:
        response = client.get("/api/v1/edge/me", headers={"X-Edge-Api-Key": api_key})
    if response.status_code != 200:
        raise SystemExit("端末キーを確認できませんでした。キーが正しいか、有効かを確認してください。")
    print("端末用APIキーを確認しました。端末は匿名化済みの記録候補を送信できます。")


if __name__ == "__main__":
    main()
