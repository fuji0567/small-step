from datetime import datetime, timezone

from sqlalchemy import event, func, select
from sqlalchemy.orm import Session

from app.database import create_database_engine
from app.models import AuditEvent, AuditEventAction, Base, School
from scripts.migrate_sqlite_to_supabase import (
    MODELS_IN_DEPENDENCY_ORDER,
    copy_application_data,
    copy_items,
)


def test_migration_covers_every_application_table_in_dependency_order():
    migrated_tables = [model.__tablename__ for model in MODELS_IN_DEPENDENCY_ORDER]

    assert set(migrated_tables) == set(Base.metadata.tables)

    positions = {table_name: index for index, table_name in enumerate(migrated_tables)}
    for table in Base.metadata.tables.values():
        for foreign_key in table.foreign_keys:
            assert positions[foreign_key.column.table.name] < positions[table.name]


def test_copy_items_preserves_every_model_column():
    created_at = datetime(2026, 9, 13, tzinfo=timezone.utc)
    source = School(
        id="school-id",
        name="移行テスト園",
        timezone="Asia/Tokyo",
        digest_time="18:30",
        created_at=created_at,
    )

    copied = copy_items([source], School)[0]

    for column in School.__table__.columns:
        assert getattr(copied, column.key) == getattr(source, column.key)


def test_copy_application_data_flushes_foreign_key_dependencies(tmp_path):
    source_engine = create_database_engine(f"sqlite:///{tmp_path}/source.db")
    target_engine = create_database_engine(f"sqlite:///{tmp_path}/target.db")

    for engine in (source_engine, target_engine):
        event.listen(engine, "connect", lambda connection, _: connection.execute("PRAGMA foreign_keys=ON"))
        Base.metadata.create_all(engine)

    with Session(source_engine) as source:
        source.add(School(id="school-id", name="移行元の園"))
        source.commit()
        source.add(
            AuditEvent(
                id="audit-id",
                school_id="school-id",
                actor_teacher_id=None,
                action=AuditEventAction.child_archived,
                target_type="child",
            )
        )
        source.commit()

    with Session(source_engine) as source, Session(target_engine) as target:
        copied_counts = copy_application_data(source, target)
        target.commit()

        assert copied_counts["schools"] == 1
        assert copied_counts["audit_events"] == 1
        assert target.scalar(select(func.count()).select_from(School)) == 1
        assert target.scalar(select(func.count()).select_from(AuditEvent)) == 1
