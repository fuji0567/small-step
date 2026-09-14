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
    latest_database_backup,
    prune_database_backup_generations,
    scheduled_backup_due,
    verify_database_backup,
)
from app.offsite_backup import (
    OffsiteBackupError,
    load_offsite_receipt,
    receipt_matches_backup,
    replicate_backup_offsite,
)


def _failure_message(error: Exception) -> str:
    if isinstance(error, (DatabaseBackupError, OffsiteBackupError)):
        return str(error)
    return f"保存領域を操作できません（{type(error).__name__}）。"


def run_backup_if_due(*, settings: Settings, now: datetime | None = None) -> bool:
    current_time = now or datetime.now(timezone.utc)
    output_dir = Path(settings.database_backup_dir)
    backup_is_due = scheduled_backup_due(
        output_dir,
        backup_time=settings.database_backup_time,
        timezone_name=settings.timezone,
        now=current_time,
    )
    if backup_is_due:
        result = create_database_backup(
            settings.database_url,
            output_dir,
            now=current_time,
        )
    elif settings.database_backup_offsite_enabled:
        result = verify_database_backup(latest_database_backup(output_dir))
        if receipt_matches_backup(load_offsite_receipt(output_dir), result):
            return False
    else:
        return False

    offsite_receipt = None
    if settings.database_backup_offsite_enabled:
        offsite_receipt = replicate_backup_offsite(
            result,
            recipient=settings.database_backup_age_recipient or "",
            bucket=settings.database_backup_s3_bucket or "",
            prefix=settings.database_backup_s3_prefix,
            endpoint_url=settings.database_backup_s3_endpoint_url,
            region_name=settings.database_backup_s3_region,
            server_side_encryption=settings.database_backup_s3_sse,
            kms_key_id=settings.database_backup_s3_kms_key_id,
            now=current_time,
        )
    removed = prune_database_backup_generations(
        output_dir,
        retention_count=settings.database_backup_retention_count,
    )
    if backup_is_due:
        print("Small Step業務データの日次バックアップを作成しました。")
    else:
        print("未完了だった外部バックアップを再送しました。")
    print(f"保存先: {result.archive_path}")
    print(f"サイズ: {result.size_bytes} bytes")
    if offsite_receipt is not None:
        print("公開鍵暗号化した外部バックアップの保存を確認しました。")
        print(f"外部保存キー: {offsite_receipt.object_key}")
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
        except (DatabaseBackupError, OffsiteBackupError, OSError) as error:
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
