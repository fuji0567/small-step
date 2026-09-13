"""Create verified daily database backups without stopping the application."""

from __future__ import annotations

import argparse
import time
from datetime import datetime, timezone
from pathlib import Path

from app.config import Settings
from app.database_backup import (
    DatabaseBackupError,
    create_database_backup,
    prune_database_backup_generations,
    scheduled_backup_due,
)


def _failure_message(error: Exception) -> str:
    if isinstance(error, DatabaseBackupError):
        return str(error)
    return f"保存領域を操作できません（{type(error).__name__}）。"


def run_backup_if_due(*, settings: Settings, now: datetime | None = None) -> bool:
    current_time = now or datetime.now(timezone.utc)
    output_dir = Path(settings.database_backup_dir)
    if not scheduled_backup_due(
        output_dir,
        backup_time=settings.database_backup_time,
        timezone_name=settings.timezone,
        now=current_time,
    ):
        return False

    result = create_database_backup(
        settings.database_url,
        output_dir,
        now=current_time,
    )
    removed = prune_database_backup_generations(
        output_dir,
        retention_count=settings.database_backup_retention_count,
    )
    print("Small Step業務データの日次バックアップを作成しました。")
    print(f"保存先: {result.archive_path}")
    print(f"サイズ: {result.size_bytes} bytes")
    if removed:
        print(f"設定済みの保持世代数を超えたローカルバックアップを{len(removed)}件削除しました。")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Small Stepの日次バックアップを管理します。")
    parser.add_argument("--watch", action="store_true", help="継続して予定時刻を確認します")
    parser.add_argument("--poll-seconds", type=float, help="確認間隔を一時的に上書きします")
    args = parser.parse_args()
    settings = Settings()
    poll_seconds = (
        args.poll_seconds
        if args.poll_seconds is not None
        else settings.database_backup_worker_poll_seconds
    )
    if poll_seconds < 30:
        raise SystemExit("--poll-seconds は30秒以上にしてください。")

    if not args.watch:
        try:
            created = run_backup_if_due(settings=settings)
        except (DatabaseBackupError, OSError) as error:
            raise SystemExit(_failure_message(error)) from error
        print("日次バックアップは作成済みです。" if not created else "日次バックアップを確認しました。")
        return

    while True:
        try:
            run_backup_if_due(settings=settings)
        except (DatabaseBackupError, OSError) as error:
            print(f"日次バックアップに失敗しました: {_failure_message(error)}")
        time.sleep(poll_seconds)


if __name__ == "__main__":
    main()
