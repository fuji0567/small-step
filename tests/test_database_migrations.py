from alembic import command
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text

from app.database import create_database_engine, initialise_database
from app.database_migrations import (
    build_alembic_config,
    migration_revision,
    prepare_database,
    upgrade_database,
)


def test_trial_migration_preserves_existing_production_school(tmp_path):
    database_url = f"sqlite:///{tmp_path}/trial-upgrade.db"
    config = build_alembic_config(database_url)
    command.upgrade(config, "0026_recorder_child_suggestions")
    engine = create_database_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(text(
                "INSERT INTO schools (id, name, timezone, digest_time, created_at) "
                "VALUES ('existing', 'Existing school', 'Asia/Tokyo', '17:00', CURRENT_TIMESTAMP)"
            ))
        command.upgrade(config, "head")
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT trial_mode FROM schools WHERE id = 'existing'")) == 0
    finally:
        engine.dispose()


def test_trial_postgresql_migration_adds_safe_defaults_without_access_changes():
    import io

    config = build_alembic_config("postgresql+psycopg://unused:unused@localhost/unused")
    config.output_buffer = output = io.StringIO()
    command.upgrade(config, "0026_recorder_child_suggestions:0027_school_trial_mode", sql=True)
    sql = output.getvalue()
    assert "trial_mode BOOLEAN DEFAULT false NOT NULL" in sql
    assert sql.count("is_trial BOOLEAN DEFAULT false NOT NULL") == 3
    assert "notificationstatus ADD VALUE IF NOT EXISTS 'trial'" in sql
    assert "school_trial_mode_changed" in sql
    assert "GRANT" not in sql and "DISABLE ROW LEVEL SECURITY" not in sql


def test_class_delivery_postgresql_migration_is_additive_and_keeps_opt_in_defaults():
    output = io.StringIO()
    config = build_alembic_config("postgresql://example:unused@localhost/example")
    config.output_buffer = output
    command.upgrade(config, "0028_teacher_invitations:0029_class_digest_delivery", sql=True)
    sql = output.getvalue()

    assert "CREATE TABLE classrooms" in sql
    assert "delivery_enabled BOOLEAN DEFAULT false NOT NULL" in sql
    assert "daily_growth_limit INTEGER DEFAULT '1' NOT NULL" in sql
    assert "ADD COLUMN classroom_id VARCHAR(36)" in sql
    assert "ADD COLUMN guardian_line_linked_at TIMESTAMP WITH TIME ZONE" in sql
    assert "ADD COLUMN growth_delivery_entry_id VARCHAR(36)" in sql
    assert "GRANT" not in sql and "DISABLE ROW LEVEL SECURITY" not in sql


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
        voiceprint_columns = {
            column["name"] for column in inspector.get_columns("teacher_voiceprints")
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
        "classrooms",
        "class_newsletters",
        "class_newsletter_recipients",
        "growth_delivery_batches",
        "growth_delivery_entries",
    } <= tables
    assert {"detected_speaker_count", "used_low_volume_retry", "candidate_category"} <= columns
    assert {
        "kind",
        "similarity_score",
        "matched",
        "claim_token",
        "sample_storage_keys",
        "quality_issue",
        "quality_sample_index",
    } <= voiceprint_job_columns
    assert "sample_count" in voiceprint_columns
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
        "claim_token",
        "processed_segment_count",
        "failed_segment_count",
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
    assert {"voiceprint_candidate_teacher_id", "voiceprint_matching_checked"} <= record_columns
    assert "candidate_child_id" in record_columns
    assert migration_revision(database_url) == "0029_class_digest_delivery"


def test_existing_local_sqlite_database_is_adopted_without_deleting_data(tmp_path):
    database_url = f"sqlite:///{tmp_path}/existing.db"
    engine = create_database_engine(database_url)
    try:
        initialise_database(engine)
    finally:
        engine.dispose()

    message = prepare_database(database_url)

    assert "登録しました" in message
    assert migration_revision(database_url) == "0029_class_digest_delivery"


def test_both_0022_branches_upgrade_to_the_merged_head(tmp_path):
    for branch_revision in (
        "0022_recording_sessions",
        "0022_voiceprint_multi_sample",
    ):
        database_url = f"sqlite:///{tmp_path}/{branch_revision}.db"
        command.upgrade(build_alembic_config(database_url), branch_revision)

        upgrade_database(database_url)

        engine = create_database_engine(database_url)
        try:
            inspector = inspect(engine)
            assert "recording_sessions" in inspector.get_table_names()
            assert "sample_count" in {
                column["name"] for column in inspector.get_columns("teacher_voiceprints")
            }
        finally:
            engine.dispose()
        assert migration_revision(database_url) == "0029_class_digest_delivery"


def test_recorder_worker_migration_preserves_existing_session_metadata(tmp_path):
    database_url = f"sqlite:///{tmp_path}/recorder-upgrade.db"
    command.upgrade(build_alembic_config(database_url), "0023_recording_voiceprint_merge")
    engine = create_database_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(text("""
                INSERT INTO recording_sessions
                (id, school_id, teacher_id, client_session_id, status, expires_at, created_at, updated_at)
                VALUES ('session', 'school', 'teacher', 'client', 'queued',
                        '2026-09-17', '2026-09-16', '2026-09-16')
            """))
        upgrade_database(database_url)
        with engine.connect() as connection:
            row = connection.execute(text("""
                SELECT status, claim_token, processed_segment_count, failed_segment_count
                FROM recording_sessions WHERE id = 'session'
            """)).one()
        assert tuple(row) == ("queued", None, 0, 0)
    finally:
        engine.dispose()


def test_recorder_worker_migration_generates_postgresql_safe_additive_sql():
    output = io.StringIO()
    config = build_alembic_config("postgresql://example:unused@localhost/example")
    config.output_buffer = output
    command.upgrade(config, "0023_recording_voiceprint_merge:0024_recorder_worker", sql=True)
    sql = output.getvalue()
    assert "ALTER TABLE recording_sessions ADD COLUMN claim_token VARCHAR(36)" in sql
    assert "processed_segment_count INTEGER DEFAULT '0' NOT NULL" in sql
    assert "failed_segment_count INTEGER DEFAULT '0' NOT NULL" in sql
    assert "GRANT" not in sql and "DISABLE ROW LEVEL SECURITY" not in sql
import io


def test_recorder_voiceprint_migration_is_opt_in_for_existing_consent(tmp_path):
    database_url = f"sqlite:///{tmp_path}/consent-upgrade.db"
    command.upgrade(build_alembic_config(database_url), "0024_recorder_worker")
    engine = create_database_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(text("""
                INSERT INTO voice_enrollment_consents
                (id, school_id, teacher_id, purpose, policy_version, retention_days,
                 consented_at, expires_at, created_at, updated_at)
                VALUES ('consent', 'school', 'teacher', 'teacher_voiceprint_enrollment',
                        'old', 30, '2026-09-17', '2026-10-17', '2026-09-17', '2026-09-17')
            """))
        upgrade_database(database_url)
        with engine.connect() as connection:
            assert connection.scalar(text(
                "SELECT allows_recorder_identification FROM voice_enrollment_consents WHERE id = 'consent'"
            )) == 0
    finally:
        engine.dispose()


def test_recorder_voiceprint_migration_preserves_postgresql_permissions():
    output = io.StringIO()
    config = build_alembic_config("postgresql://example:unused@localhost/example")
    config.output_buffer = output
    command.upgrade(config, "0024_recorder_worker:0025_recorder_voiceprint", sql=True)
    sql = output.getvalue()
    assert "allows_recorder_identification BOOLEAN DEFAULT false NOT NULL" in sql
    assert "voiceprint_candidate_teacher_id VARCHAR(36)" in sql
    assert "voiceprint_matching_checked BOOLEAN DEFAULT false NOT NULL" in sql
    assert "GRANT" not in sql and "DISABLE ROW LEVEL SECURITY" not in sql


def test_child_advice_migration_preserves_existing_children_and_has_no_selection(tmp_path):
    database_url = f"sqlite:///{tmp_path}/child-advice-upgrade.db"
    command.upgrade(build_alembic_config(database_url), "0025_recorder_voiceprint")
    engine = create_database_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(text("""
                INSERT INTO children (id, school_id, display_name, is_active, created_at)
                VALUES ('child', 'school', 'Existing name', 1, '2026-09-18')
            """))
        upgrade_database(database_url)
        with engine.connect() as connection:
            row = connection.execute(text("SELECT display_name, recording_names FROM children WHERE id = 'child'")).one()
            assert row == ("Existing name", "[]")
            assert "candidate_child_id" in {column["name"] for column in inspect(engine).get_columns("records")}
    finally:
        engine.dispose()


def test_child_advice_migration_preserves_postgresql_permissions():
    output = io.StringIO()
    config = build_alembic_config("postgresql://example:unused@localhost/example")
    config.output_buffer = output
    command.upgrade(config, "0025_recorder_voiceprint:0026_recorder_child_suggestions", sql=True)
    sql = output.getvalue()
    assert "recording_names JSON DEFAULT '[]' NOT NULL" in sql
    assert "candidate_child_id VARCHAR(36)" in sql
    assert "GRANT" not in sql and "DISABLE ROW LEVEL SECURITY" not in sql
