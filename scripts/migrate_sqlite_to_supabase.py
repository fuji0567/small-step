"""One-time, non-destructive migration from the local SQLite prototype.

It copies existing application records to a *new, empty* Supabase PostgreSQL
database while preserving IDs. The target is never overwritten.
"""

from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import func, select

from app.config import Settings
from app.database import create_database_engine, create_session_factory, initialise_database
from app.models import Child, Notification, Record, School, Teacher


SOURCE_DATABASE_URL = "sqlite:///./data/otayori.db"
MODELS_IN_DEPENDENCY_ORDER = (School, Teacher, Child, Record, Notification)
COPY_FIELDS: dict[type[object], tuple[str, ...]] = {
    School: ("id", "name", "timezone", "created_at"),
    Teacher: ("id", "school_id", "name", "email", "auth_user_id", "role", "created_at"),
    Child: ("id", "school_id", "display_name", "guardian_line_user_id", "created_at"),
    Record: (
        "id",
        "school_id",
        "teacher_id",
        "child_id",
        "category",
        "status",
        "source_event_id",
        "confidence",
        "occurred_at",
        "summary",
        "conversation_prompt",
        "anonymized_context",
        "reviewed_at",
        "created_at",
        "updated_at",
    ),
    Notification: (
        "id",
        "record_id",
        "channel",
        "recipient_line_user_id",
        "scheduled_for",
        "status",
        "provider_message_id",
        "sent_at",
        "created_at",
    ),
}


def item_count(session, model: type[object]) -> int:
    return int(session.scalar(select(func.count()).select_from(model)) or 0)


def copy_items(source_items: Iterable[object], model: type[object]) -> list[object]:
    return [model(**{field: getattr(item, field) for field in COPY_FIELDS[model]}) for item in source_items]


def main() -> None:
    settings = Settings()
    if settings.database_url.startswith("sqlite"):
        raise SystemExit("DATABASE_URL がまだSQLiteです。先に configure_supabase_database.py を実行してください。")

    source_engine = create_database_engine(SOURCE_DATABASE_URL)
    target_engine = create_database_engine(settings.database_url)
    initialise_database(source_engine)
    initialise_database(target_engine)
    SourceSession = create_session_factory(source_engine)
    TargetSession = create_session_factory(target_engine)

    try:
        with SourceSession() as source, TargetSession() as target:
            target_counts = {model.__tablename__: item_count(target, model) for model in MODELS_IN_DEPENDENCY_ORDER}
            if any(target_counts.values()):
                raise SystemExit(
                    "Supabase側に既存データがあるため中止しました（上書きはしません）。"
                )

            copied_counts: dict[str, int] = {}
            for model in MODELS_IN_DEPENDENCY_ORDER:
                items = source.scalars(select(model)).all()
                target.add_all(copy_items(items, model))
                copied_counts[model.__tablename__] = len(items)
            target.commit()

        print("SQLiteからSupabase PostgreSQLへコピーしました。")
        print("件数:", copied_counts)
    finally:
        source_engine.dispose()
        target_engine.dispose()


if __name__ == "__main__":
    main()
