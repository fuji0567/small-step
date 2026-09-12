from datetime import datetime, timezone

from app.models import Base, School
from scripts.migrate_sqlite_to_supabase import MODELS_IN_DEPENDENCY_ORDER, copy_items


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
