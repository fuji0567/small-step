"""Client-encrypted replication of verified database backups to S3-compatible storage."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import subprocess
import tempfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.database_backup import BackupVerification, DatabaseBackupError


OFFSITE_STATE_FILENAME = ".small-step-offsite-backup.json"
CommandRunner = Callable[..., subprocess.CompletedProcess[str]]


class OffsiteBackupError(RuntimeError):
    """Raised when a backup cannot be encrypted or confirmed off site."""


@dataclass(frozen=True)
class OffsiteBackupReceipt:
    archive_name: str
    archive_sha256: str
    object_key: str
    encrypted_size_bytes: int
    encrypted_sha256: str
    uploaded_at: datetime


def offsite_state_path(backup_dir: Path) -> Path:
    return backup_dir / OFFSITE_STATE_FILENAME


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalise_object_key(prefix: str, filename: str) -> str:
    parts = [part for part in prefix.strip("/").split("/") if part]
    if any(part in {".", ".."} for part in parts):
        raise OffsiteBackupError("S3保存先プレフィックスに使用できない値があります。")
    return "/".join([*parts, filename])


def encrypt_backup_with_age(
    verification: BackupVerification,
    *,
    recipient: str,
    runner: CommandRunner = subprocess.run,
) -> Path:
    """Encrypt one verified archive with an offline-held age identity."""

    archive_path = verification.archive_path
    if archive_path.is_symlink() or not archive_path.is_file():
        raise OffsiteBackupError("暗号化するバックアップを安全に読み取れません。")
    try:
        actual_sha256 = _sha256(archive_path)
    except OSError as error:
        raise OffsiteBackupError("暗号化するバックアップを読み取れません。") from error
    if not hmac.compare_digest(actual_sha256, verification.sha256):
        raise OffsiteBackupError("暗号化前にバックアップの検証値が変化しました。")
    destination = archive_path.parent / f".{archive_path.name}.{os.getpid()}.age.tmp"
    destination.unlink(missing_ok=True)
    try:
        result = runner(
            [
                "age",
                "--encrypt",
                "--recipient",
                recipient,
                "--output",
                str(destination),
                str(archive_path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as error:
        raise OffsiteBackupError("age暗号化コマンドを実行できません。") from error
    if result.returncode != 0:
        destination.unlink(missing_ok=True)
        raise OffsiteBackupError("バックアップの公開鍵暗号化に失敗しました。")
    if destination.is_symlink() or not destination.is_file() or destination.stat().st_size == 0:
        destination.unlink(missing_ok=True)
        raise OffsiteBackupError("暗号化後のバックアップが空です。")
    destination.chmod(0o600)
    return destination


def create_s3_client(
    *,
    endpoint_url: str | None,
    region_name: str | None,
) -> Any:
    try:
        import boto3
    except ImportError as error:
        raise OffsiteBackupError("S3転送用ライブラリを利用できません。") from error

    options: dict[str, str] = {}
    if endpoint_url:
        options["endpoint_url"] = endpoint_url
    if region_name:
        options["region_name"] = region_name
    return boto3.client("s3", **options)


def _save_receipt(backup_dir: Path, receipt: OffsiteBackupReceipt) -> None:
    backup_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    payload = {
        "version": 1,
        "archive_name": receipt.archive_name,
        "archive_sha256": receipt.archive_sha256,
        "object_key": receipt.object_key,
        "encrypted_size_bytes": receipt.encrypted_size_bytes,
        "encrypted_sha256": receipt.encrypted_sha256,
        "uploaded_at": receipt.uploaded_at.astimezone(timezone.utc).isoformat(),
    }
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=backup_dir,
            prefix=f".{OFFSITE_STATE_FILENAME}.",
            delete=False,
        ) as stream:
            temporary_path = Path(stream.name)
            json.dump(payload, stream, ensure_ascii=True, separators=(",", ":"))
            stream.flush()
            os.fsync(stream.fileno())
        temporary_path.chmod(0o600)
        temporary_path.replace(offsite_state_path(backup_dir))
        temporary_path = None
        offsite_state_path(backup_dir).chmod(0o600)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def load_offsite_receipt(backup_dir: Path) -> OffsiteBackupReceipt | None:
    path = offsite_state_path(backup_dir)
    if not path.exists() or path.is_symlink() or not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("version") != 1:
            return None
        uploaded_at = datetime.fromisoformat(payload["uploaded_at"])
        if uploaded_at.tzinfo is None:
            uploaded_at = uploaded_at.replace(tzinfo=timezone.utc)
        receipt = OffsiteBackupReceipt(
            archive_name=str(payload["archive_name"]),
            archive_sha256=str(payload["archive_sha256"]),
            object_key=str(payload["object_key"]),
            encrypted_size_bytes=int(payload["encrypted_size_bytes"]),
            encrypted_sha256=str(payload["encrypted_sha256"]),
            uploaded_at=uploaded_at.astimezone(timezone.utc),
        )
        if (
            not receipt.archive_name.startswith("small-step-public-")
            or not receipt.archive_name.endswith(".dump")
            or len(receipt.archive_sha256) != 64
            or len(receipt.encrypted_sha256) != 64
            or receipt.encrypted_size_bytes <= 0
        ):
            return None
        return receipt
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError):
        return None


def receipt_matches_backup(
    receipt: OffsiteBackupReceipt | None,
    verification: BackupVerification,
) -> bool:
    return bool(
        receipt is not None
        and receipt.archive_name == verification.archive_path.name
        and receipt.archive_sha256 == verification.sha256
    )


def replicate_backup_offsite(
    verification: BackupVerification,
    *,
    recipient: str,
    bucket: str,
    prefix: str,
    endpoint_url: str | None,
    region_name: str | None,
    server_side_encryption: str,
    kms_key_id: str | None = None,
    s3_client: Any | None = None,
    runner: CommandRunner = subprocess.run,
    now: datetime | None = None,
) -> OffsiteBackupReceipt:
    """Encrypt, upload, and confirm one archive before recording success."""

    encrypted_path = encrypt_backup_with_age(
        verification,
        recipient=recipient,
        runner=runner,
    )
    try:
        encrypted_size = encrypted_path.stat().st_size
        encrypted_sha256 = _sha256(encrypted_path)
        object_key = _normalise_object_key(prefix, f"{verification.archive_path.name}.age")
        client = s3_client or create_s3_client(
            endpoint_url=endpoint_url,
            region_name=region_name,
        )
        extra_args: dict[str, object] = {
            "Metadata": {
                "small-step-format": "age-v1",
                "source-sha256": verification.sha256,
                "encrypted-sha256": encrypted_sha256,
            },
        }
        if server_side_encryption != "none":
            extra_args["ServerSideEncryption"] = server_side_encryption
        if server_side_encryption == "aws:kms" and kms_key_id:
            extra_args["SSEKMSKeyId"] = kms_key_id
        try:
            client.upload_file(
                str(encrypted_path),
                bucket,
                object_key,
                ExtraArgs=extra_args,
            )
            head = client.head_object(Bucket=bucket, Key=object_key)
        except Exception as error:
            raise OffsiteBackupError("暗号化バックアップの外部保存を確認できません。") from error

        try:
            raw_metadata = head.get("Metadata", {})
            metadata: Mapping[str, str] = (
                raw_metadata if isinstance(raw_metadata, Mapping) else {}
            )
            remote_size = int(head.get("ContentLength", -1))
            encryption_matches = (
                server_side_encryption == "none"
                or head.get("ServerSideEncryption") == server_side_encryption
            )
        except (AttributeError, TypeError, ValueError) as error:
            raise OffsiteBackupError("外部保存先の確認応答を解釈できません。") from error
        if (
            remote_size != encrypted_size
            or metadata.get("source-sha256") != verification.sha256
            or metadata.get("encrypted-sha256") != encrypted_sha256
            or not encryption_matches
        ):
            raise OffsiteBackupError("外部保存先のサイズ、検証値、または暗号化方式が一致しません。")

        uploaded_at = now or datetime.now(timezone.utc)
        if uploaded_at.tzinfo is None:
            uploaded_at = uploaded_at.replace(tzinfo=timezone.utc)
        receipt = OffsiteBackupReceipt(
            archive_name=verification.archive_path.name,
            archive_sha256=verification.sha256,
            object_key=object_key,
            encrypted_size_bytes=encrypted_size,
            encrypted_sha256=encrypted_sha256,
            uploaded_at=uploaded_at.astimezone(timezone.utc),
        )
        _save_receipt(verification.archive_path.parent, receipt)
        return receipt
    finally:
        encrypted_path.unlink(missing_ok=True)
