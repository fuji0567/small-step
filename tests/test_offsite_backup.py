import hashlib
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.database_backup import BackupVerification
from app.offsite_backup import (
    OffsiteBackupError,
    load_offsite_receipt,
    replicate_backup_offsite,
)


NOW = datetime(2026, 9, 14, 3, 0, tzinfo=timezone.utc)


def verification(tmp_path: Path) -> BackupVerification:
    archive = tmp_path / "small-step-public-20260914T030000000000Z.dump"
    archive.write_bytes(b"verified database backup")
    return BackupVerification(
        archive_path=archive,
        size_bytes=archive.stat().st_size,
        sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
        table_names=frozenset({"schools"}),
    )


def age_runner(command, **_kwargs):
    destination = Path(command[command.index("--output") + 1])
    source = Path(command[-1])
    destination.write_bytes(b"age-encrypted\n" + source.read_bytes())
    return subprocess.CompletedProcess(command, 0, "", "")


class FakeS3Client:
    def __init__(self, *, tamper: bool = False):
        self.tamper = tamper
        self.upload = None

    def upload_file(self, filename, bucket, key, *, ExtraArgs):
        self.upload = {
            "filename": filename,
            "bucket": bucket,
            "key": key,
            "extra_args": ExtraArgs,
            "size": Path(filename).stat().st_size,
        }

    def head_object(self, *, Bucket, Key):
        assert self.upload is not None
        assert (Bucket, Key) == (self.upload["bucket"], self.upload["key"])
        metadata = dict(self.upload["extra_args"]["Metadata"])
        if self.tamper:
            metadata["encrypted-sha256"] = "0" * 64
        return {
            "ContentLength": self.upload["size"],
            "Metadata": metadata,
            "ServerSideEncryption": self.upload["extra_args"]["ServerSideEncryption"],
        }


def test_replicate_backup_encrypts_uploads_verifies_and_saves_receipt(tmp_path):
    result = verification(tmp_path)
    client = FakeS3Client()

    receipt = replicate_backup_offsite(
        result,
        recipient="age1examplepublicrecipient",
        bucket="small-step-backups",
        prefix="school-a/database",
        endpoint_url="https://s3.example.test",
        region_name="ap-northeast-1",
        server_side_encryption="AES256",
        s3_client=client,
        runner=age_runner,
        now=NOW,
    )

    assert receipt.archive_name == result.archive_path.name
    assert receipt.object_key == f"school-a/database/{result.archive_path.name}.age"
    assert receipt.uploaded_at == NOW
    assert client.upload["extra_args"]["Metadata"]["source-sha256"] == result.sha256
    assert not list(tmp_path.glob(".*.age.tmp"))
    assert load_offsite_receipt(tmp_path) == receipt
    assert (tmp_path / ".small-step-offsite-backup.json").stat().st_mode & 0o777 == 0o600


def test_replicate_backup_rejects_unconfirmed_remote_and_removes_temporary_file(tmp_path):
    with pytest.raises(OffsiteBackupError, match="一致しません"):
        replicate_backup_offsite(
            verification(tmp_path),
            recipient="age1examplepublicrecipient",
            bucket="small-step-backups",
            prefix="database",
            endpoint_url=None,
            region_name=None,
            server_side_encryption="AES256",
            s3_client=FakeS3Client(tamper=True),
            runner=age_runner,
            now=NOW,
        )

    assert load_offsite_receipt(tmp_path) is None
    assert not list(tmp_path.glob(".*.age.tmp"))


def test_replicate_backup_rejects_unsafe_object_prefix(tmp_path):
    with pytest.raises(OffsiteBackupError, match="プレフィックス"):
        replicate_backup_offsite(
            verification(tmp_path),
            recipient="age1examplepublicrecipient",
            bucket="small-step-backups",
            prefix="../database",
            endpoint_url=None,
            region_name=None,
            server_side_encryption="AES256",
            s3_client=FakeS3Client(),
            runner=age_runner,
            now=NOW,
        )


def test_replicate_backup_rejects_archive_changed_after_verification(tmp_path):
    result = verification(tmp_path)
    result.archive_path.write_bytes(b"changed after verification")

    with pytest.raises(OffsiteBackupError, match="検証値が変化"):
        replicate_backup_offsite(
            result,
            recipient="age1examplepublicrecipient",
            bucket="small-step-backups",
            prefix="database",
            endpoint_url=None,
            region_name=None,
            server_side_encryption="AES256",
            s3_client=FakeS3Client(),
            runner=age_runner,
            now=NOW,
        )
