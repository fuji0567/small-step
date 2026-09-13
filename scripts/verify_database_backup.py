"""Verify the newest Small Step database backup without restoring it."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from app.database_backup import (
    DatabaseBackupError,
    latest_database_backup,
    verify_database_backup,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Small Step業務データのバックアップを検証します。")
    parser.add_argument("archive", nargs="?", type=Path, help="省略時は最新のバックアップを確認")
    args = parser.parse_args()
    output_dir = Path(os.getenv("DATABASE_BACKUP_DIR", "./data/database-backups"))
    try:
        archive = args.archive or latest_database_backup(output_dir)
        result = verify_database_backup(archive)
    except DatabaseBackupError as error:
        raise SystemExit(str(error)) from error

    print("バックアップのチェックサムと構成は正常です。")
    print(f"対象: {result.archive_path}")
    print(f"サイズ: {result.size_bytes} bytes")
    print(f"確認済みテーブル数: {len(result.table_names)}")


if __name__ == "__main__":
    main()
