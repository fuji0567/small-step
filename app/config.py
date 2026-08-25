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
    line_channel_secret: str | None = None
    line_channel_access_token: str | None = None
    line_api_timeout_seconds: float = 10.0
    notion_api_token: str | None = None
    notion_data_source_id: str | None = None
    notion_api_timeout_seconds: float = 10.0
    edge_audio_inbox_dir: str = "./data/edge-audio-inbox"
    edge_audio_max_file_bytes: int = 25_000_000
    edge_audio_delete_after_processing: bool = True
    edge_audio_language: str = "ja"
    edge_audio_model: str = "small"
    edge_audio_device: str = "cpu"
    edge_audio_compute_type: str = "int8"
    llm_base_url: str | None = None
    llm_api_key: str | None = None
    llm_model: str | None = None
    llm_allow_external: bool = False
    llm_timeout_seconds: float = 60.0
    edge_api_url: str = "http://127.0.0.1:8000"
    edge_api_key: str | None = None
    edge_api_timeout_seconds: float = 15.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
