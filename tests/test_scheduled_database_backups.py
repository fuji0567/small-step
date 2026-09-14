from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.config import Settings
from app.offsite_backup import OffsiteBackupError
from scripts.schedule_database_backups import run_backup_if_due


NOW = datetime(2026, 9, 14, 3, 0, tzinfo=timezone.utc)


def test_scheduled_worker_does_nothing_when_today_is_already_backed_up(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "scripts.schedule_database_backups.scheduled_backup_due",
        lambda *_args, **_kwargs: False,
    )
    monkeypatch.setattr(
        "scripts.schedule_database_backups.create_database_backup",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("backup must not run")),
    )
    settings = Settings(database_backup_dir=str(tmp_path))

    assert run_backup_if_due(settings=settings, now=NOW) is False


def test_scheduled_worker_creates_then_applies_explicit_retention(tmp_path, monkeypatch, capsys):
    archive = tmp_path / "small-step-public-test.dump"
    created: list[tuple[str, Path, datetime]] = []
    pruned: list[tuple[Path, int]] = []
    monkeypatch.setattr(
        "scripts.schedule_database_backups.scheduled_backup_due",
        lambda *_args, **_kwargs: True,
    )

    def fake_create(database_url, output_dir, *, now):
        created.append((database_url, output_dir, now))
        return SimpleNamespace(archive_path=archive, size_bytes=123)

    def fake_prune(output_dir, *, retention_count):
        pruned.append((output_dir, retention_count))
        return (tmp_path / "old.dump",)

    monkeypatch.setattr(
        "scripts.schedule_database_backups.create_database_backup",
        fake_create,
    )
    monkeypatch.setattr(
        "scripts.schedule_database_backups.prune_database_backup_generations",
        fake_prune,
    )
    settings = Settings(
        database_url="postgresql+psycopg://user:password@db.example.test/postgres",
        database_backup_dir=str(tmp_path),
        database_backup_retention_count=7,
    )

    assert run_backup_if_due(settings=settings, now=NOW) is True
    assert created == [(settings.database_url, tmp_path, NOW)]
    assert pruned == [(tmp_path, 7)]
    output = capsys.readouterr().out
    assert "日次バックアップを作成しました" in output
    assert "1件削除しました" in output


def test_scheduled_worker_does_not_prune_when_offsite_copy_fails(tmp_path, monkeypatch):
    archive = tmp_path / "small-step-public-test.dump"
    monkeypatch.setattr(
        "scripts.schedule_database_backups.scheduled_backup_due",
        lambda *_args, **_kwargs: True,
    )
    monkeypatch.setattr(
        "scripts.schedule_database_backups.create_database_backup",
        lambda *_args, **_kwargs: SimpleNamespace(archive_path=archive, size_bytes=123),
    )
    monkeypatch.setattr(
        "scripts.schedule_database_backups.replicate_backup_offsite",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OffsiteBackupError("upload failed")),
    )
    monkeypatch.setattr(
        "scripts.schedule_database_backups.prune_database_backup_generations",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("must not prune")),
    )
    settings = Settings(
        database_url="postgresql+psycopg://user:password@db.example.test/postgres",
        database_backup_dir=str(tmp_path),
        database_backup_retention_count=7,
        database_backup_offsite_enabled=True,
        database_backup_age_recipient="age1examplepublicrecipient",
        database_backup_s3_bucket="small-step-backups",
    )

    with pytest.raises(OffsiteBackupError, match="upload failed"):
        run_backup_if_due(settings=settings, now=NOW)


def test_scheduled_worker_retries_missing_offsite_copy_without_creating_new_backup(
    tmp_path,
    monkeypatch,
):
    archive = tmp_path / "small-step-public-test.dump"
    verification = SimpleNamespace(archive_path=archive, size_bytes=123, sha256="a" * 64)
    replicated = []
    monkeypatch.setattr(
        "scripts.schedule_database_backups.scheduled_backup_due",
        lambda *_args, **_kwargs: False,
    )
    monkeypatch.setattr(
        "scripts.schedule_database_backups.latest_database_backup",
        lambda *_args, **_kwargs: archive,
    )
    monkeypatch.setattr(
        "scripts.schedule_database_backups.verify_database_backup",
        lambda *_args, **_kwargs: verification,
    )
    monkeypatch.setattr(
        "scripts.schedule_database_backups.load_offsite_receipt",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "scripts.schedule_database_backups.create_database_backup",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("must not create")),
    )
    monkeypatch.setattr(
        "scripts.schedule_database_backups.replicate_backup_offsite",
        lambda result, **_kwargs: replicated.append(result)
        or SimpleNamespace(object_key="database/test.dump.age"),
    )
    monkeypatch.setattr(
        "scripts.schedule_database_backups.prune_database_backup_generations",
        lambda *_args, **_kwargs: (),
    )
    settings = Settings(
        database_url="postgresql+psycopg://user:password@db.example.test/postgres",
        database_backup_dir=str(tmp_path),
        database_backup_offsite_enabled=True,
        database_backup_age_recipient="age1examplepublicrecipient",
        database_backup_s3_bucket="small-step-backups",
    )

    assert run_backup_if_due(settings=settings, now=NOW) is True
    assert replicated == [verification]
