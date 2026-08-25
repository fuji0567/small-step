"""Create the Small Step Notion database beneath a shared parent page."""

import getpass

from app.config import get_settings
from app.notion import NotionSyncError, create_small_step_database


def main() -> None:
    settings = get_settings()
    api_token = settings.notion_api_token or getpass.getpass("Notion installation token: ").strip()
    parent_page_id = input("Shared parent page ID: ").strip()
    if not api_token or not parent_page_id:
        raise SystemExit("Both the Notion token and parent page ID are required.")

    try:
        database_id, data_source_id = create_small_step_database(
            api_token=api_token,
            parent_page_id=parent_page_id,
            timeout_seconds=settings.notion_api_timeout_seconds,
        )
    except NotionSyncError as error:
        raise SystemExit(f"Notion setup failed: {error}") from error

    print("Notion database created successfully.")
    print(f"Database ID: {database_id}")
    print(f"Set NOTION_DATA_SOURCE_ID={data_source_id} in .env, then restart the API.")


if __name__ == "__main__":
    main()
