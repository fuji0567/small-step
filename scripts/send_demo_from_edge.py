"""Send one labelled, anonymized test candidate to a running local API server."""

from __future__ import annotations

from datetime import datetime, timezone
import getpass
from uuid import uuid4

import httpx


DEFAULT_API_URL = "http://127.0.0.1:8000"


def main() -> None:
    api_url = input(f"API URL（Enterで {DEFAULT_API_URL}）: ").strip() or DEFAULT_API_URL
    api_key = getpass.getpass("Edge device API key（画面には表示されません）: ")
    if not api_key:
        raise SystemExit("APIキーを入力してください。")

    payload = {
        "category": "growth",
        "source_event_id": f"edge-demo-{uuid4()}",
        "confidence": 0.93,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "summary": "【端末テスト】友だちと協力して遊びの片付けに取り組みました。",
        "conversation_prompt": "今日はどんなお片付けを頑張ったのかな？",
        "anonymized_context": "端末APIの動作確認用に作成した匿名化済み要約です。",
    }
    try:
        response = httpx.post(
            f"{api_url.rstrip('/')}/api/v1/edge/records",
            headers={"X-Edge-Api-Key": api_key},
            json=payload,
            timeout=15,
        )
    except httpx.HTTPError as exc:
        raise SystemExit(f"起動中のAPIへ接続できませんでした: {exc}") from exc
    if response.status_code != 201:
        raise SystemExit(f"記録候補の送信に失敗しました（HTTP {response.status_code}）。")
    print("端末から匿名化済みの成長記録候補を送信しました。先生の承認待ちです。")


if __name__ == "__main__":
    main()
