"""Small Step database migration helpers.

SQLite stays convenient for local development.  VRT and PostgreSQL deployments
use these helpers so their schema changes are explicit, reviewable, and
repeatable through Alembic.
"""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text

from app.database import create_database_engine, initialise_database


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APPLICATION_TABLES = (
    "schools", "teachers", "records", "notifications", "classrooms",
    "class_newsletters", "class_newsletter_recipients",
    "growth_delivery_batches", "growth_delivery_entries",
)


class DatabaseMigrationError(RuntimeError):
    """Raised when an existing production database needs a deliberate review."""


def build_alembic_config(database_url: str) -> Config:
    """Create an Alembic configuration without putting a database URL in Git."""

    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(PROJECT_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def upgrade_database(database_url: str) -> None:
    """Apply every reviewed migration to a fresh or already managed database."""

    command.upgrade(build_alembic_config(database_url), "head")


def migration_revision(database_url: str) -> str | None:
    """Return the applied Alembic revision without exposing connection details."""

    engine = create_database_engine(database_url)
    try:
        inspector = inspect(engine)
        if not inspector.has_table("alembic_version"):
            return None
        with engine.connect() as connection:
            return connection.scalar(text("SELECT version_num FROM alembic_version LIMIT 1"))
    finally:
        engine.dispose()


def latest_migration_revision() -> str | None:
    """Return the latest reviewed migration identifier from this source tree."""

    config = build_alembic_config("sqlite://")
    return ScriptDirectory.from_config(config).get_current_head()


def prepare_database(database_url: str) -> str:
    """Prepare a database safely before running a deployed API.

    Empty databases receive the initial migration.  Existing local SQLite
    prototype databases are first brought up to the current local schema and
    then marked as adopted.  Existing non-SQLite databases without migration
    history stop rather than risking an accidental production overwrite.
    """

    engine = create_database_engine(database_url)
    try:
        revision = migration_revision(database_url)
        if revision is not None:
            action = "upgrade"
        else:
            inspector = inspect(engine)
            has_application_tables = any(inspector.has_table(name) for name in APPLICATION_TABLES)
            if not has_application_tables:
                action = "upgrade"
            elif engine.dialect.name == "sqlite":
                initialise_database(engine)
                action = "adopt"
            else:
                raise DatabaseMigrationError(
                    "このPostgreSQLにはSmall Stepの既存テーブルがありますが、"
                    "移行履歴がありません。バックアップを確認してから手動で移行してください。"
                )
    finally:
        engine.dispose()

    config = build_alembic_config(database_url)
    if action == "adopt":
        command.stamp(config, "head")
        return "既存のローカルSQLiteデータベースを移行管理へ登録しました。"

    command.upgrade(config, "head")
    return "データベースを最新の移行状態に更新しました。"
