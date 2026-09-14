"""One-time, non-destructive migration from the local SQLite prototype.

It copies existing application records to a *new, empty* Supabase PostgreSQL
database while preserving IDs. The target is never overwritten.
"""

from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import func, select

from app.config import Settings
from app.database import create_database_engine, create_session_factory, initialise_database
from app.database_migrations import upgrade_database
from app.models import (
    AuditEvent,
    Child,
    CloudAudioJob,
    EdgeDevice,
    GuardianArchiveLink,
    LineLinkInvitation,
    NotionSync,
    Notification,
    Record,
    School,
    Teacher,
    TeacherVoiceprint,
    VoiceEnrollmentConsent,
    VoiceprintJob,
    WorkerHeartbeat,
)


SOURCE_DATABASE_URL = "sqlite:///./data/otayori.db"
MODELS_IN_DEPENDENCY_ORDER = (
    School,
    Teacher,
    Child,
    EdgeDevice,
    VoiceEnrollmentConsent,
    TeacherVoiceprint,
    LineLinkInvitation,
    GuardianArchiveLink,
    AuditEvent,
    Record,
    CloudAudioJob,
    VoiceprintJob,
    Notification,
    NotionSync,
    WorkerHeartbeat,
)


def item_count(session, model: type[object]) -> int:
    return int(session.scalar(select(func.count()).select_from(model)) or 0)


def copy_items(source_items: Iterable[object], model: type[object]) -> list[object]:
    fields = tuple(column.key for column in model.__table__.columns)
    return [model(**{field: getattr(item, field) for field in fields}) for item in source_items]


def copy_application_data(source, target) -> dict[str, int]:
    """Copy every table and flush each dependency layer before continuing."""

    copied_counts: dict[str, int] = {}
    for model in MODELS_IN_DEPENDENCY_ORDER:
        items = source.scalars(select(model)).all()
        target.add_all(copy_items(items, model))
        # The models intentionally do not define ORM relationships. Flushing
        # here guarantees that referenced rows exist before dependent tables.
        target.flush()
        copied_counts[model.__tablename__] = len(items)
    return copied_counts


def main() -> None:
    settings = Settings()
    if settings.database_url.startswith("sqlite"):
        raise SystemExit("DATABASE_URL がまだSQLiteです。先に configure_supabase_database.py を実行してください。")

    source_engine = create_database_engine(SOURCE_DATABASE_URL)
    target_engine = create_database_engine(settings.database_url)
    initialise_database(source_engine)
    upgrade_database(settings.database_url)
    SourceSession = create_session_factory(source_engine)
    TargetSession = create_session_factory(target_engine)

    try:
        with SourceSession() as source, TargetSession() as target:
            target_counts = {model.__tablename__: item_count(target, model) for model in MODELS_IN_DEPENDENCY_ORDER}
            if any(target_counts.values()):
                raise SystemExit(
                    "Supabase側に既存データがあるため中止しました（上書きはしません）。"
                )

            copied_counts = copy_application_data(source, target)
            target.commit()

        print("SQLiteからSupabase PostgreSQLへコピーしました。")
        print("件数:", copied_counts)
    finally:
        source_engine.dispose()
        target_engine.dispose()


if __name__ == "__main__":
    main()
