from alembic.script import ScriptDirectory
from sqlalchemy import inspect

from app.database import create_database_engine, initialise_database
from app.database_migrations import (
    build_alembic_config,
    migration_revision,
    prepare_database,
    upgrade_database,
)


def test_revision_identifiers_fit_the_postgresql_version_column():
    script = ScriptDirectory.from_config(build_alembic_config("sqlite://"))

    assert all(len(revision.revision) <= 128 for revision in script.walk_revisions())


def test_initial_migration_creates_the_current_schema(tmp_path):
    database_url = f"sqlite:///{tmp_path}/fresh.db"

    upgrade_database(database_url)

    engine = create_database_engine(database_url)
    try:
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        columns = {column["name"] for column in inspector.get_columns("cloud_audio_jobs")}
    finally:
        engine.dispose()

    assert {
        "alembic_version",
        "schools",
        "cloud_audio_jobs",
        "audit_events",
        "notion_syncs",
        "worker_heartbeats",
    } <= tables
    assert {"detected_speaker_count", "used_low_volume_retry", "candidate_category"} <= columns
    assert migration_revision(database_url) == "0020_record_reassignment_audit"


def test_existing_local_sqlite_database_is_adopted_without_deleting_data(tmp_path):
    database_url = f"sqlite:///{tmp_path}/existing.db"
    engine = create_database_engine(database_url)
    try:
        initialise_database(engine)
    finally:
        engine.dispose()

    message = prepare_database(database_url)

    assert "登録しました" in message
    assert migration_revision(database_url) == "0020_record_reassignment_audit"
