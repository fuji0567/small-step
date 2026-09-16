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
        voiceprint_job_columns = {
            column["name"] for column in inspector.get_columns("voiceprint_jobs")
        }
        recording_session_columns = {
            column["name"] for column in inspector.get_columns("recording_sessions")
        }
        recording_segment_columns = {
            column["name"] for column in inspector.get_columns("recording_segments")
        }
        record_columns = {column["name"] for column in inspector.get_columns("records")}
    finally:
        engine.dispose()

    assert {
        "alembic_version",
        "schools",
        "cloud_audio_jobs",
        "audit_events",
        "notion_syncs",
        "worker_heartbeats",
        "teacher_voiceprints",
        "voiceprint_jobs",
        "recording_sessions",
        "recording_segments",
    } <= tables
    assert {"detected_speaker_count", "used_low_volume_retry", "candidate_category"} <= columns
    assert {"kind", "similarity_score", "matched", "claim_token"} <= voiceprint_job_columns
    assert {
        "id",
        "school_id",
        "teacher_id",
        "client_session_id",
        "status",
        "record_id",
        "expires_at",
        "created_at",
        "updated_at",
    } <= recording_session_columns
    assert {
        "id",
        "session_id",
        "sequence",
        "duration_ms",
        "size_bytes",
        "sha256",
        "media_type",
        "storage_key",
    } <= recording_segment_columns
    assert "audio_processing_incomplete" in record_columns
    assert migration_revision(database_url) == "0022_recording_sessions"


def test_existing_local_sqlite_database_is_adopted_without_deleting_data(tmp_path):
    database_url = f"sqlite:///{tmp_path}/existing.db"
    engine = create_database_engine(database_url)
    try:
        initialise_database(engine)
    finally:
        engine.dispose()

    message = prepare_database(database_url)

    assert "登録しました" in message
    assert migration_revision(database_url) == "0022_recording_sessions"
