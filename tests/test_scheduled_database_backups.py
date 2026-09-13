from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from app.config import Settings
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
