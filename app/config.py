from functools import lru_cache
from typing import Literal
from urllib.parse import urlparse

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables or a local .env file."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: Literal["development", "production"] = "development"
    database_url: str = "sqlite:///./data/otayori.db"
    auth_mode: Literal["development", "supabase"] = "development"
    supabase_url: str | None = None
    supabase_publishable_key: str | None = None
    supabase_bootstrap_admin_emails: str = ""
    digest_time: str = Field(default="17:00", pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    timezone: str = "Asia/Tokyo"
    line_channel_secret: str | None = None
    line_channel_access_token: str | None = None
    line_api_timeout_seconds: float = 10.0
    line_worker_poll_seconds: float = Field(default=15.0, ge=1.0, le=3_600.0)
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
    edge_audio_watch_poll_seconds: float = Field(default=2.0, gt=0)
    edge_audio_watch_min_age_seconds: float = Field(default=2.0, ge=0)
    edge_audio_retry_initial_seconds: float = Field(default=10.0, ge=1.0, le=3_600.0)
    edge_audio_retry_max_seconds: float = Field(default=300.0, ge=1.0, le=86_400.0)
    edge_audio_record_chunk_seconds: float = Field(default=30.0, gt=0)
    edge_audio_input_device: str = ":0"
    edge_audio_processing_mode: Literal["local", "cloud"] = "local"
    cloud_audio_enabled: bool = False
    cloud_audio_job_dir: str = "./data/cloud-audio-jobs"
    cloud_audio_job_retention_minutes: int = Field(default=15, ge=1, le=1_440)
    cloud_audio_processing_timeout_minutes: int = Field(default=10, ge=1, le=1_440)
    cloud_audio_worker_poll_seconds: float = Field(default=2.0, gt=0)
    worker_heartbeat_interval_seconds: float = Field(default=30.0, ge=5.0, le=3_600.0)
    worker_heartbeat_stale_seconds: float = Field(default=90.0, ge=10.0, le=7_200.0)
    speaker_diarization_model: str = "pyannote/speaker-diarization-community-1"
    speaker_diarization_token: str | None = None
    speaker_diarization_device: str = "cpu"
    speaker_diarization_low_volume_retry: bool = True
    llm_backend: Literal["ollama", "vllm"] = "ollama"
    llm_base_url: str | None = None
    llm_api_key: str | None = None
    llm_model: str | None = None
    llm_allow_external: bool = False
    llm_timeout_seconds: float = 60.0
    edge_api_url: str = "http://127.0.0.1:8000"
    edge_api_key: str | None = None
    edge_api_timeout_seconds: float = 15.0
    edge_device_heartbeat_interval_seconds: float = Field(default=60.0, ge=5.0, le=3_600.0)
    guardian_archive_enabled: bool = False
    guardian_archive_base_url: str = "http://127.0.0.1:8000"
    guardian_archive_link_ttl_hours: int = Field(default=168, ge=1, le=720)

    @model_validator(mode="after")
    def reject_unsafe_production_configuration(self) -> "Settings":
        """Keep local defaults from accidentally becoming a public deployment."""

        if self.worker_heartbeat_stale_seconds <= self.worker_heartbeat_interval_seconds:
            raise ValueError(
                "WORKER_HEARTBEAT_STALE_SECONDS must be greater than WORKER_HEARTBEAT_INTERVAL_SECONDS"
            )
        if self.app_env != "production":
            return self

        if self.auth_mode != "supabase":
            raise ValueError("Production requires AUTH_MODE=supabase")
        if not self.supabase_url or not self.supabase_publishable_key:
            raise ValueError("Production requires SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY")
        if self.database_url.startswith("sqlite:"):
            raise ValueError("Production requires a non-SQLite DATABASE_URL")
        if self.guardian_archive_enabled:
            archive_url = urlparse(self.guardian_archive_base_url)
            if archive_url.scheme != "https" or not archive_url.netloc:
                raise ValueError("Guardian archive requires an HTTPS GUARDIAN_ARCHIVE_BASE_URL in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
