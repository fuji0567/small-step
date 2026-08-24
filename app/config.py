from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables or a local .env file."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    database_url: str = "sqlite:///./data/otayori.db"
    auth_mode: Literal["development", "supabase"] = "development"
    supabase_url: str | None = None
    supabase_publishable_key: str | None = None
    supabase_bootstrap_admin_emails: str = ""
    digest_time: str = "17:00"
    timezone: str = "Asia/Tokyo"


@lru_cache
def get_settings() -> Settings:
    return Settings()
