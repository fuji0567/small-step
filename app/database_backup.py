"""Safe PostgreSQL backup and restore-rehearsal helpers.

The archive intentionally contains only Small Step's ``public`` schema. Supabase
Auth and Storage are managed separately by Supabase and are not copied here.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import subprocess
import tempfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.engine import URL, make_url


CORE_APPLICATION_TABLES = frozenset(
    {
        "alembic_version",
        "children",
        "notifications",
        "records",
        "schools",
        "teachers",
    }
)
LOCAL_RESTORE_HOSTS = frozenset({"127.0.0.1", "::1", "localhost", "restore-db"})
CommandRunner = Callable[..., subprocess.CompletedProcess[str]]


class DatabaseBackupError(RuntimeError):
    """Raised when a backup cannot be created or safely rehearsed."""


@dataclass(frozen=True)
class BackupVerification:
    archive_path: Path
    size_bytes: int
    sha256: str
    table_names: frozenset[str]


@dataclass(frozen=True)
class RestoreRehearsal:
    archive_path: Path
    table_count: int
    row_counts: Mapping[str, int]


def _postgres_url(database_url: str) -> URL:
    try:
        url = make_url(database_url)
    except Exception as error:
        raise DatabaseBackupError("DATABASE_URLをPostgreSQL接続先として解釈できません。") from error

    if url.get_backend_name() != "postgresql":
        raise DatabaseBackupError("バックアップ対象にはPostgreSQLのDATABASE_URLが必要です。")
    if not url.host or not url.database or not url.username:
        raise DatabaseBackupError("DATABASE_URLにはホスト、データベース名、ユーザー名が必要です。")
    return url


def postgres_environment(
    database_url: str,
    *,
    base_environment: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Convert a SQLAlchemy URL to libpq variables without exposing it in argv."""

    url = _postgres_url(database_url)
    environment = dict(base_environment or os.environ)
    for variable_name in tuple(environment):
        if variable_name.startswith("PG"):
            environment.pop(variable_name)
    environment.update(
        {
            "PGHOST": url.host or "",
            "PGPORT": str(url.port or 5432),
            "PGDATABASE": url.database or "",
            "PGUSER": url.username or "",
            "PGCONNECT_TIMEOUT": str(url.query.get("connect_timeout", "15")),
        }
    )
    if url.password is not None:
        environment["PGPASSWORD"] = url.password

    option_names = {
        "application_name": "PGAPPNAME",
        "sslcert": "PGSSLCERT",
        "sslkey": "PGSSLKEY",
        "sslmode": "PGSSLMODE",
        "sslrootcert": "PGSSLROOTCERT",
        "target_session_attrs": "PGTARGETSESSIONATTRS",
    }
    for query_name, environment_name in option_names.items():
        value = url.query.get(query_name)
        if value:
            environment[environment_name] = str(value)

    if "PGSSLMODE" not in environment and (url.host or "").lower() not in LOCAL_RESTORE_HOSTS:
        environment["PGSSLMODE"] = "require"
    return environment


def connection_fingerprint(database_url: str) -> tuple[str, int, str, str]:
    """Identify a database without including its password."""

    url = _postgres_url(database_url)
    return (
        (url.host or "").lower(),
        url.port or 5432,
        url.database or "",
        url.username or "",
    )


def _run_checked(
    command: Sequence[str],
    *,
    environment: Mapping[str, str] | None = None,
    runner: CommandRunner = subprocess.run,
) -> str:
    try:
        result = runner(
            list(command),
            env=dict(environment) if environment is not None else None,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as error:
        raise DatabaseBackupError(f"必要なコマンドを実行できません: {command[0]}") from error
    if result.returncode != 0:
        raise DatabaseBackupError(
            f"{command[0]}が失敗しました（終了コード {result.returncode}）。接続設定とログを確認してください。"
        )
    return result.stdout


def _version_major(output: str) -> int:
    match = re.search(r"(?:^|\s)(\d+)(?:\.\d+)?(?:\s|$)", output.strip())
    if not match:
        raise DatabaseBackupError("PostgreSQLのバージョンを確認できませんでした。")
    return int(match.group(1))


def ensure_dump_client_compatible(
    database_url: str,
    *,
    runner: CommandRunner = subprocess.run,
) -> tuple[int, int]:
    environment = postgres_environment(database_url)
    client_output = _run_checked(["pg_dump", "--version"], runner=runner)
    server_output = _run_checked(
        ["psql", "--tuples-only", "--no-align", "--command", "SHOW server_version_num"],
        environment=environment,
        runner=runner,
    )
    client_major = _version_major(client_output)
    try:
        server_major = int(server_output.strip()) // 10_000
    except ValueError as error:
        raise DatabaseBackupError("Supabase PostgreSQLのバージョンを確認できませんでした。") from error
    if client_major < server_major:
        raise DatabaseBackupError(
            "バックアップ用PostgreSQLクライアントが接続先より古いため中止しました。"
        )
    return client_major, server_major


def archive_table_names(listing: str) -> frozenset[str]:
    table_names: set[str] = set()
    for line in listing.splitlines():
        if line.startswith(";"):
            continue
        match = re.search(r"\sTABLE\s+public\s+([^\s]+)\s", line)
        if match:
            table_names.add(match.group(1).strip('"'))
    return frozenset(table_names)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def checksum_path(archive_path: Path) -> Path:
    return Path(f"{archive_path}.sha256")


def backup_checksum_is_valid(archive_path: Path) -> bool:
    """Validate one archive/checksum pair without invoking PostgreSQL tools."""

    if archive_path.is_symlink() or not archive_path.is_file():
        return False
    digest_path = checksum_path(archive_path)
    if digest_path.is_symlink() or not digest_path.is_file():
        return False
    try:
        parts = digest_path.read_text(encoding="ascii").strip().split(maxsplit=1)
        if len(parts) != 2 or parts[1] != archive_path.name or len(parts[0]) != 64:
            return False
        actual_digest = _sha256(archive_path)
    except (OSError, UnicodeError):
        return False
    return hmac.compare_digest(parts[0], actual_digest)


def _assert_core_tables(table_names: frozenset[str]) -> None:
    missing = sorted(CORE_APPLICATION_TABLES - table_names)
    if missing:
        raise DatabaseBackupError(
            "バックアップに必要な業務テーブルがありません: " + ", ".join(missing)
        )


def create_database_backup(
    database_url: str,
    output_dir: Path,
    *,
    now: datetime | None = None,
    runner: CommandRunner = subprocess.run,
) -> BackupVerification:
    """Create and verify an atomic custom-format dump of the public schema."""

    ensure_dump_client_compatible(database_url, runner=runner)
    if output_dir.is_symlink():
        raise DatabaseBackupError("バックアップ先にシンボリックリンクは使用できません。")
    output_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    output_dir.chmod(0o700)

    timestamp = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    archive_path = output_dir / timestamp.strftime("small-step-public-%Y%m%dT%H%M%S%fZ.dump")
    if archive_path.exists():
        raise DatabaseBackupError("同じ作成時刻のバックアップがすでに存在します。")
    environment = postgres_environment(database_url)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=output_dir,
            prefix=".small-step-public-",
            suffix=".dump",
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
        temporary_path.chmod(0o600)
        _run_checked(
            [
                "pg_dump",
                "--format=custom",
                "--compress=9",
                "--no-owner",
                "--no-privileges",
                "--schema=public",
                "--lock-wait-timeout=30000",
                "--file",
                str(temporary_path),
            ],
            environment=environment,
            runner=runner,
        )
        if not temporary_path.is_file() or temporary_path.stat().st_size == 0:
            raise DatabaseBackupError("作成されたバックアップが空です。")

        listing = _run_checked(["pg_restore", "--list", str(temporary_path)], runner=runner)
        table_names = archive_table_names(listing)
        _assert_core_tables(table_names)
        temporary_path.replace(archive_path)
        temporary_path = None
        archive_path.chmod(0o600)

        digest = _sha256(archive_path)
        digest_path = checksum_path(archive_path)
        with digest_path.open("x", encoding="ascii") as stream:
            stream.write(f"{digest}  {archive_path.name}\n")
        digest_path.chmod(0o600)
        return BackupVerification(archive_path, archive_path.stat().st_size, digest, table_names)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def verify_database_backup(
    archive_path: Path,
    *,
    runner: CommandRunner = subprocess.run,
) -> BackupVerification:
    if archive_path.is_symlink():
        raise DatabaseBackupError("指定されたバックアップファイルを安全に読み取れません。")
    archive_path = archive_path.resolve()
    if not archive_path.is_file():
        raise DatabaseBackupError("指定されたバックアップファイルを安全に読み取れません。")
    digest_path = checksum_path(archive_path)
    if not digest_path.is_file() or digest_path.is_symlink():
        raise DatabaseBackupError("対応するSHA-256チェックサムがありません。")

    parts = digest_path.read_text(encoding="ascii").strip().split(maxsplit=1)
    if len(parts) != 2 or parts[1] != archive_path.name:
        raise DatabaseBackupError("チェックサムファイルの形式が正しくありません。")
    actual_digest = _sha256(archive_path)
    if not hmac.compare_digest(parts[0], actual_digest):
        raise DatabaseBackupError("バックアップのSHA-256チェックサムが一致しません。")

    listing = _run_checked(["pg_restore", "--list", str(archive_path)], runner=runner)
    table_names = archive_table_names(listing)
    _assert_core_tables(table_names)
    return BackupVerification(archive_path, archive_path.stat().st_size, actual_digest, table_names)


def latest_database_backup(output_dir: Path) -> Path:
    backups = sorted(output_dir.glob("small-step-public-*.dump"))
    if not backups:
        raise DatabaseBackupError("確認できるデータベースバックアップがありません。")
    return backups[-1]


def scheduled_backup_due(
    output_dir: Path,
    *,
    backup_time: str,
    timezone_name: str,
    now: datetime | None = None,
) -> bool:
    """Return whether the latest scheduled daily backup is still missing."""

    try:
        hour, minute = (int(part) for part in backup_time.split(":"))
        if hour not in range(24) or minute not in range(60):
            raise ValueError
        local_timezone = ZoneInfo(timezone_name)
    except (TypeError, ValueError, ZoneInfoNotFoundError) as error:
        raise DatabaseBackupError("バックアップ時刻またはタイムゾーンが正しくありません。") from error

    current_time = now or datetime.now(timezone.utc)
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)
    local_now = current_time.astimezone(local_timezone)
    latest_schedule = local_now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if local_now < latest_schedule:
        latest_schedule -= timedelta(days=1)

    try:
        latest_archive = latest_database_backup(output_dir)
        if not backup_checksum_is_valid(latest_archive):
            return True
        modified_at = datetime.fromtimestamp(latest_archive.stat().st_mtime, tz=timezone.utc)
    except (DatabaseBackupError, OSError):
        return True
    return modified_at < latest_schedule.astimezone(timezone.utc)


def prune_database_backup_generations(
    output_dir: Path,
    *,
    retention_count: int,
) -> tuple[Path, ...]:
    """Remove complete archive/checksum pairs beyond an explicit local limit."""

    if retention_count < 0:
        raise DatabaseBackupError("バックアップ保持世代数は0以上にしてください。")
    if retention_count == 0:
        return ()

    archives = sorted(
        archive
        for archive in output_dir.glob("small-step-public-*.dump")
        if archive.is_file()
        and not archive.is_symlink()
        and checksum_path(archive).is_file()
        and not checksum_path(archive).is_symlink()
    )
    candidates = archives[:-retention_count]
    removed: list[Path] = []
    for archive in candidates:
        digest_path = checksum_path(archive)
        archive.unlink()
        digest_path.unlink()
        removed.append(archive)
    return tuple(removed)


def _query_integer(
    sql: str,
    *,
    environment: Mapping[str, str],
    runner: CommandRunner,
) -> int:
    output = _run_checked(
        ["psql", "--tuples-only", "--no-align", "--command", sql],
        environment=environment,
        runner=runner,
    )
    try:
        return int(output.strip())
    except ValueError as error:
        raise DatabaseBackupError("復元確認用データベースの応答を解釈できません。") from error


def rehearse_database_restore(
    archive_path: Path,
    *,
    production_database_url: str,
    restore_database_url: str,
    runner: CommandRunner = subprocess.run,
) -> RestoreRehearsal:
    """Restore an archive only into an empty, local, disposable database."""

    verification = verify_database_backup(archive_path, runner=runner)
    target_url = _postgres_url(restore_database_url)
    if (target_url.host or "").lower() not in LOCAL_RESTORE_HOSTS:
        raise DatabaseBackupError("復元リハーサル先はローカルの使い捨てDBだけ指定できます。")
    if connection_fingerprint(production_database_url) == connection_fingerprint(restore_database_url):
        raise DatabaseBackupError("本番データベースを復元先には指定できません。")

    environment = postgres_environment(restore_database_url)
    existing_tables = _query_integer(
        "SELECT count(*) FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_type = 'BASE TABLE'",
        environment=environment,
        runner=runner,
    )
    if existing_tables:
        raise DatabaseBackupError("復元先が空ではないため中止しました。使い捨てDBを作り直してください。")

    _run_checked(
        [
            "pg_restore",
            "--clean",
            "--if-exists",
            "--exit-on-error",
            "--single-transaction",
            "--no-owner",
            "--no-privileges",
            "--dbname",
            target_url.database or "",
            str(verification.archive_path),
        ],
        environment=environment,
        runner=runner,
    )
    table_count = _query_integer(
        "SELECT count(*) FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_type = 'BASE TABLE'",
        environment=environment,
        runner=runner,
    )
    if table_count < len(CORE_APPLICATION_TABLES):
        raise DatabaseBackupError("復元後の業務テーブル数が不足しています。")

    row_counts = {
        table_name: _query_integer(
            f'SELECT count(*) FROM public."{table_name}"',
            environment=environment,
            runner=runner,
        )
        for table_name in sorted(CORE_APPLICATION_TABLES - {"alembic_version"})
    }
    return RestoreRehearsal(verification.archive_path, table_count, row_counts)
