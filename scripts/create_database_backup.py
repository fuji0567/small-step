"""Create a verified backup of Small Step application data."""

from __future__ import annotations

import os
from pathlib import Path

from app.config import Settings
from app.database_backup import DatabaseBackupError, create_database_backup


def main() -> None:
    settings = Settings()
    output_dir = Path(os.getenv("DATABASE_BACKUP_DIR", "./data/database-backups"))
    try:
        result = create_database_backup(settings.database_url, output_dir)
    except DatabaseBackupError as error:
        raise SystemExit(str(error)) from error

    print("Small Step業務データのバックアップを作成しました。")
    print(f"保存先: {result.archive_path}")
    print(f"サイズ: {result.size_bytes} bytes")
    print(f"確認済みテーブル数: {len(result.table_names)}")
    print("音声ファイル、Supabase Authユーザー、Supabase Storageは含まれません。")


if __name__ == "__main__":
    main()
