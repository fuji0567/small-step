from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.models import Base


def create_database_engine(database_url: str) -> Engine:
    if database_url.startswith("sqlite:///") and not database_url.endswith(":memory:"):
        database_path = Path(database_url.removeprefix("sqlite:///"))
        database_path.parent.mkdir(parents=True, exist_ok=True)
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    return create_engine(database_url, connect_args=connect_args, pool_pre_ping=True)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def initialise_database(engine: Engine) -> None:
    """Prepare only local SQLite databases for quick development.

    Production PostgreSQL is created and updated by Alembic migrations.  This
    deliberate split prevents a newly deployed API process from silently
    changing the production schema while keeping the local prototype simple.
    """

    if engine.dialect.name != "sqlite":
        return

    Base.metadata.create_all(bind=engine)
    with engine.begin() as connection:
        for table, name, definition in (
            ("teachers", "invitation_attempted_at", "DATETIME"),
            ("teachers", "invitation_sent_at", "DATETIME"),
            ("schools", "trial_mode", "BOOLEAN NOT NULL DEFAULT 0"),
            ("records", "is_trial", "BOOLEAN NOT NULL DEFAULT 0"),
            ("recording_sessions", "is_trial", "BOOLEAN NOT NULL DEFAULT 0"),
            ("cloud_audio_jobs", "is_trial", "BOOLEAN NOT NULL DEFAULT 0"),
            ("children", "recording_names", "JSON NOT NULL DEFAULT '[]'"),
            ("children", "classroom_id", "VARCHAR(36)"),
            ("children", "guardian_line_linked_at", "DATETIME"),
            ("notifications", "growth_delivery_entry_id", "VARCHAR(36)"),
            ("classrooms", "delivery_enabled_since", "DATETIME"),
            ("class_newsletter_recipients", "child_ids", "JSON NOT NULL DEFAULT '[]'"),
            ("records", "candidate_child_id", "VARCHAR(36)"),
            ("voice_enrollment_consents", "allows_recorder_identification", "BOOLEAN NOT NULL DEFAULT 0"),
            ("records", "voiceprint_candidate_teacher_id", "VARCHAR(36)"),
            ("records", "voiceprint_matching_checked", "BOOLEAN NOT NULL DEFAULT 0"),
        ):
            if name not in {column["name"] for column in inspect(engine).get_columns(table)}:
                connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {definition}"))
    # This project started with a SQLite prototype before Auth was introduced.
    # Keep local developer databases usable without forcing a destructive reset.
    columns = {column["name"] for column in inspect(engine).get_columns("teachers")}
    with engine.begin() as connection:
        connection.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_notifications_growth_delivery_entry "
            "ON notifications (growth_delivery_entry_id)"
        ))
        if "auth_user_id" not in columns:
            connection.execute(text("ALTER TABLE teachers ADD COLUMN auth_user_id VARCHAR(36)"))
            connection.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS ix_teachers_auth_user_id "
                    "ON teachers (auth_user_id)"
                )
            )
        if "role" not in columns:
            connection.execute(
                text("ALTER TABLE teachers ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'teacher'"))


def get_db_session(session_factory: sessionmaker[Session]) -> Generator[Session, None, None]:
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
