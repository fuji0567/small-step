"""Prepare the Small Step database before a VRT/API deployment."""

from app.config import Settings
from app.database_migrations import DatabaseMigrationError, prepare_database


def main() -> None:
    try:
        message = prepare_database(Settings().database_url)
    except DatabaseMigrationError as error:
        raise SystemExit(f"データベースの更新を中止しました: {error}") from error
    print(message)


if __name__ == "__main__":
    main()
