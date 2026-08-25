"""Small, server-side helpers for syncing delivered notices to Notion."""

from datetime import datetime

import httpx


NOTION_API_BASE_URL = "https://api.notion.com/v1"
NOTION_VERSION = "2026-03-11"
NOTION_RICH_TEXT_LIMIT = 2_000


class NotionSyncError(RuntimeError):
    """Raised when a Notion request cannot create the expected page."""


def rich_text(value: str) -> list[dict[str, object]]:
    """Split text at Notion's per-text-object length limit."""

    if not value:
        return []
    return [
        {"type": "text", "text": {"content": value[index : index + NOTION_RICH_TEXT_LIMIT]}}
        for index in range(0, len(value), NOTION_RICH_TEXT_LIMIT)
    ]


def _headers(api_token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json",
        "Notion-Version": NOTION_VERSION,
    }


def _raise_for_notion_error(response: httpx.Response) -> None:
    if not response.is_success:
        raise NotionSyncError(f"Notion API returned HTTP {response.status_code}")


def _select_option(category: str) -> str:
    return "けが" if category == "injury" else "成長"


def create_delivered_notification_page(
    *,
    api_token: str,
    data_source_id: str,
    school_name: str,
    child_name: str | None,
    record_id: str,
    category: str,
    occurred_at: datetime,
    reviewed_at: datetime | None,
    sent_at: datetime,
    summary: str,
    conversation_prompt: str | None,
    timeout_seconds: float,
) -> tuple[str, str | None]:
    """Create one page containing only teacher-approved, already-sent content."""

    title = f"{child_name or '園児未指定'} - {_select_option(category)}"
    children: list[dict[str, object]] = [
        {
            "object": "block",
            "type": "heading_2",
            "heading_2": {"rich_text": rich_text("通知本文")},
        },
        {
            "object": "block",
            "type": "paragraph",
            "paragraph": {"rich_text": rich_text(summary)},
        },
    ]
    if conversation_prompt:
        children.extend(
            [
                {
                    "object": "block",
                    "type": "heading_2",
                    "heading_2": {"rich_text": rich_text("保護者への補足")},
                },
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {"rich_text": rich_text(conversation_prompt)},
                },
            ]
        )

    response = httpx.post(
        f"{NOTION_API_BASE_URL}/pages",
        headers=_headers(api_token),
        json={
            "parent": {"type": "data_source_id", "data_source_id": data_source_id},
            "properties": {
                "タイトル": {"title": rich_text(title)},
                "園": {"rich_text": rich_text(school_name)},
                "園児": {"rich_text": rich_text(child_name or "園児未指定")},
                "分類": {"select": {"name": _select_option(category)}},
                "状態": {"select": {"name": "LINE送信済み"}},
                "発生日時": {"date": {"start": occurred_at.isoformat()}},
                "承認日時": {"date": {"start": reviewed_at.isoformat()} if reviewed_at else None},
                "LINE送信日時": {"date": {"start": sent_at.isoformat()}},
                "記録ID": {"rich_text": rich_text(record_id)},
            },
            "children": children,
        },
        timeout=timeout_seconds,
    )
    _raise_for_notion_error(response)
    payload = response.json()
    page_id = payload.get("id")
    if not isinstance(page_id, str) or not page_id:
        raise NotionSyncError("Notion API response did not include a page ID")
    page_url = payload.get("url")
    return page_id, page_url if isinstance(page_url, str) else None


def create_small_step_database(
    *,
    api_token: str,
    parent_page_id: str,
    timeout_seconds: float,
) -> tuple[str, str]:
    """Create the fixed data source schema expected by this integration."""

    response = httpx.post(
        f"{NOTION_API_BASE_URL}/databases",
        headers=_headers(api_token),
        json={
            "parent": {"type": "page_id", "page_id": parent_page_id},
            "title": rich_text("Small Step 通知記録"),
            "description": rich_text("Small StepからLINE送信済みのお知らせを記録します。"),
            "initial_data_source": {
                "properties": {
                    "タイトル": {"title": {}},
                    "園": {"rich_text": {}},
                    "園児": {"rich_text": {}},
                    "分類": {"select": {"options": [{"name": "成長"}, {"name": "けが"}]}},
                    "状態": {"select": {"options": [{"name": "LINE送信済み"}]}},
                    "発生日時": {"date": {}},
                    "承認日時": {"date": {}},
                    "LINE送信日時": {"date": {}},
                    "記録ID": {"rich_text": {}},
                }
            },
        },
        timeout=timeout_seconds,
    )
    _raise_for_notion_error(response)
    payload = response.json()
    database_id = payload.get("id")
    data_sources = payload.get("data_sources")
    if not isinstance(database_id, str) or not isinstance(data_sources, list) or not data_sources:
        raise NotionSyncError("Notion API response did not include the new data source")
    data_source_id = data_sources[0].get("id") if isinstance(data_sources[0], dict) else None
    if not isinstance(data_source_id, str) or not data_source_id:
        raise NotionSyncError("Notion API response did not include a data source ID")
    return database_id, data_source_id
