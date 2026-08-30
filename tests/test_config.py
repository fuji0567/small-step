import pytest
from pydantic import ValidationError

from app.config import Settings


def production_settings(**overrides):
    return {
        "app_env": "production",
        "database_url": "postgresql+psycopg://small_step:password@db.example.test:5432/small_step",
        "auth_mode": "supabase",
        "supabase_url": "https://project.supabase.co",
        "supabase_publishable_key": "sb_publishable_test",
        **overrides,
    }


def test_production_settings_reject_local_authentication_and_sqlite():
    with pytest.raises(ValidationError, match="AUTH_MODE=supabase"):
        Settings(**production_settings(auth_mode="development"))

    with pytest.raises(ValidationError, match="non-SQLite DATABASE_URL"):
        Settings(**production_settings(database_url="sqlite:///./data/otayori.db"))


def test_production_settings_require_supabase_public_configuration():
    with pytest.raises(ValidationError, match="SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY"):
        Settings(**production_settings(supabase_publishable_key=None))


def test_guardian_archive_requires_https_only_in_production():
    with pytest.raises(ValidationError, match="HTTPS GUARDIAN_ARCHIVE_BASE_URL"):
        Settings(
            **production_settings(
                guardian_archive_enabled=True,
                guardian_archive_base_url="http://small-step.example.test",
            )
        )

    settings = Settings(
        **production_settings(
            guardian_archive_enabled=True,
            guardian_archive_base_url="https://small-step.example.test",
        )
    )
    assert settings.app_env == "production"
