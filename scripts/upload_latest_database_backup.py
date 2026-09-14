"""Encrypt and upload the latest verified database backup."""

from pathlib import Path

from app.config import Settings
from app.database_backup import DatabaseBackupError, latest_database_backup, verify_database_backup
from app.offsite_backup import OffsiteBackupError, replicate_backup_offsite


def main() -> None:
    try:
        settings = Settings()
        if not settings.database_backup_offsite_enabled:
            raise OffsiteBackupError("DATABASE_BACKUP_OFFSITE_ENABLED=true を設定してください。")
        backup_dir = Path(settings.database_backup_dir)
        verification = verify_database_backup(latest_database_backup(backup_dir))
        receipt = replicate_backup_offsite(
            verification,
            recipient=settings.database_backup_age_recipient or "",
            bucket=settings.database_backup_s3_bucket or "",
            prefix=settings.database_backup_s3_prefix,
            endpoint_url=settings.database_backup_s3_endpoint_url,
            region_name=settings.database_backup_s3_region,
            server_side_encryption=settings.database_backup_s3_sse,
            kms_key_id=settings.database_backup_s3_kms_key_id,
        )
    except (DatabaseBackupError, OffsiteBackupError, OSError) as error:
        raise SystemExit(str(error)) from error

    print("最新バックアップを公開鍵暗号化して外部保存しました。")
    print(f"対象: {receipt.archive_name}")
    print(f"外部保存キー: {receipt.object_key}")


if __name__ == "__main__":
    main()
