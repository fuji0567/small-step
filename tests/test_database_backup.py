import hashlib
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.database_backup import (
    CORE_APPLICATION_TABLES,
    DatabaseBackupError,
    archive_table_names,
    checksum_path,
    create_database_backup,
    postgres_environment,
    rehearse_database_restore,
    verify_database_backup,
)


DATABASE_URL = (
    "postgresql+psycopg://small_step:p%40ss%3Aword@db.example.test:6543/small_step"
    "?sslmode=verify-full"
)


def archive_listing() -> str:
    return "\n".join(
        f"1; 1259 1 TABLE public {table_name} postgres"
        for table_name in sorted(CORE_APPLICATION_TABLES | {"audit_events"})
    )


def completed(command, stdout="", returncode=0):
    return subprocess.CompletedProcess(command, returncode, stdout=stdout, stderr="")


def test_postgres_environment_keeps_password_out_of_connection_arguments():
    environment = postgres_environment(
        DATABASE_URL,
        base_environment={"PATH": "/bin", "PGPASSWORD": "stale", "PGSERVICE": "stale"},
    )

    assert environment["PGHOST"] == "db.example.test"
    assert environment["PGPORT"] == "6543"
    assert environment["PGDATABASE"] == "small_step"
    assert environment["PGUSER"] == "small_step"
    assert environment["PGPASSWORD"] == "p@ss:word"
    assert environment["PGSSLMODE"] == "verify-full"
    assert "PGSERVICE" not in environment


def test_postgres_environment_rejects_sqlite():
    with pytest.raises(DatabaseBackupError, match="PostgreSQL"):
        postgres_environment("sqlite:///data/local.db")


def test_archive_table_names_ignores_table_data_and_other_schemas():
    listing = "\n".join(
        [
            "1; 1259 1 TABLE public schools postgres",
            "2; 0 1 TABLE DATA public schools postgres",
            "3; 1259 2 TABLE auth users postgres",
        ]
    )

    assert archive_table_names(listing) == frozenset({"schools"})


def test_create_and_verify_database_backup(tmp_path):
    commands: list[list[str]] = []

    def runner(command, **kwargs):
        commands.append(command)
        if command[:2] == ["pg_dump", "--version"]:
            return completed(command, "pg_dump (PostgreSQL) 18.6\n")
        if command[0] == "psql":
            assert kwargs["env"]["PGPASSWORD"] == "p@ss:word"
            return completed(command, "170012\n")
        if command[0] == "pg_dump":
            output_path = Path(command[command.index("--file") + 1])
            output_path.write_bytes(b"test custom archive")
            return completed(command)
        if command[:2] == ["pg_restore", "--list"]:
            return completed(command, archive_listing())
        raise AssertionError(command)

    result = create_database_backup(
        DATABASE_URL,
        tmp_path / "backups",
        now=datetime(2026, 9, 14, 1, 2, 3, tzinfo=timezone.utc),
        runner=runner,
    )
    verified = verify_database_backup(result.archive_path, runner=runner)

    assert result.archive_path.name == "small-step-public-20260914T010203000000Z.dump"
    assert result.archive_path.stat().st_mode & 0o777 == 0o600
    assert result.archive_path.parent.stat().st_mode & 0o777 == 0o700
    assert verified.sha256 == hashlib.sha256(b"test custom archive").hexdigest()
    assert CORE_APPLICATION_TABLES <= verified.table_names
    assert all("p@ss:word" not in " ".join(command) for command in commands)


def test_verify_database_backup_rejects_modified_archive(tmp_path):
    archive = tmp_path / "small-step-public-test.dump"
    archive.write_bytes(b"before")
    checksum_path(archive).write_text(
        f"{hashlib.sha256(b'before').hexdigest()}  {archive.name}\n",
        encoding="ascii",
    )
    archive.write_bytes(b"after")

    with pytest.raises(DatabaseBackupError, match="一致しません"):
        verify_database_backup(archive)


def test_dump_client_must_not_be_older_than_server(tmp_path):
    def runner(command, **kwargs):
        if command[:2] == ["pg_dump", "--version"]:
            return completed(command, "pg_dump (PostgreSQL) 16.4\n")
        return completed(command, "170012\n")

    with pytest.raises(DatabaseBackupError, match="古い"):
        create_database_backup(DATABASE_URL, tmp_path, runner=runner)


def test_restore_rehearsal_uses_only_empty_local_database(tmp_path):
    archive = tmp_path / "small-step-public-test.dump"
    archive.write_bytes(b"archive")
    checksum_path(archive).write_text(
        f"{hashlib.sha256(b'archive').hexdigest()}  {archive.name}\n",
        encoding="ascii",
    )
    base_table_queries = 0
    restore_commands: list[list[str]] = []

    def runner(command, **kwargs):
        nonlocal base_table_queries
        if command[:2] == ["pg_restore", "--list"]:
            return completed(command, archive_listing())
        if command[0] == "pg_restore":
            restore_commands.append(command)
            return completed(command)
        if "information_schema.tables" in command[-1]:
            base_table_queries += 1
            return completed(command, "0\n" if base_table_queries == 1 else "12\n")
        if command[0] == "psql":
            return completed(command, "1\n")
        raise AssertionError(command)

    result = rehearse_database_restore(
        archive,
        production_database_url=DATABASE_URL,
        restore_database_url="postgresql+psycopg://postgres@restore-db:5432/small_step_restore",
        runner=runner,
    )

    assert result.table_count == 12
    assert set(result.row_counts) == CORE_APPLICATION_TABLES - {"alembic_version"}
    assert "--clean" in restore_commands[0]
    assert "--if-exists" in restore_commands[0]
    assert "--single-transaction" in restore_commands[0]
    assert "db.example.test" not in " ".join(restore_commands[0])


def test_restore_rehearsal_rejects_remote_target_before_connecting(tmp_path):
    archive = tmp_path / "small-step-public-test.dump"
    archive.write_bytes(b"archive")
    checksum_path(archive).write_text(
        f"{hashlib.sha256(b'archive').hexdigest()}  {archive.name}\n",
        encoding="ascii",
    )

    def runner(command, **kwargs):
        if command[:2] == ["pg_restore", "--list"]:
            return completed(command, archive_listing())
        raise AssertionError("remote restore should stop before connecting")

    with pytest.raises(DatabaseBackupError, match="使い捨てDB"):
        rehearse_database_restore(
            archive,
            production_database_url=DATABASE_URL,
            restore_database_url="postgresql://postgres@production.example.test/postgres",
            runner=runner,
        )
