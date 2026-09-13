"""Restore the newest backup into a disposable local PostgreSQL database."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from app.config import Settings
from app.database_backup import (
    DatabaseBackupError,
    latest_database_backup,
    rehearse_database_restore,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="使い捨てDBでバックアップの復元を確認します。")
    parser.add_argument("archive", nargs="?", type=Path, help="省略時は最新のバックアップを使用")
    args = parser.parse_args()
    output_dir = Path(os.getenv("DATABASE_BACKUP_DIR", "./data/database-backups"))
    restore_database_url = os.getenv("RESTORE_DATABASE_URL")
    if not restore_database_url:
        raise SystemExit("RESTORE_DATABASE_URLが設定されていません。")

    try:
        archive = args.archive or latest_database_backup(output_dir)
        result = rehearse_database_restore(
            archive,
            production_database_url=Settings().database_url,
            restore_database_url=restore_database_url,
        )
    except DatabaseBackupError as error:
        raise SystemExit(str(error)) from error

    print("使い捨てPostgreSQLへの復元リハーサルに成功しました。")
    print(f"対象: {result.archive_path}")
    print(f"復元済みテーブル数: {result.table_count}")
    print("主要データ件数:")
    for table_name, count in result.row_counts.items():
        print(f"- {table_name}: {count}")


if __name__ == "__main__":
    main()
