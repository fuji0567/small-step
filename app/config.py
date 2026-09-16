import base64
import binascii
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
    # Independent /rec recorder settings. 25 MB is ample for a one-minute
    # AAC/WebM segment while still bounding request and disk usage.
    recorder_enabled: bool = False
    recorder_session_dir: str = "data/edge-audio-inbox/recorder-sessions"
    recorder_retention_hours: int = Field(default=24, ge=1, le=720)
    recorder_max_duration_minutes: int = Field(default=60, ge=1, le=1_440)
    recorder_max_draft_sessions: int = Field(default=3, ge=1, le=100)
    recorder_max_segment_bytes: int = Field(default=25_000_000, ge=1, le=1_000_000_000)
    recorder_worker_heartbeat_required: bool = True
    recorder_processing_timeout_minutes: int = Field(default=10, ge=1, le=120)
    worker_heartbeat_interval_seconds: float = Field(default=30.0, ge=5.0, le=3_600.0)
    worker_heartbeat_stale_seconds: float = Field(default=90.0, ge=10.0, le=7_200.0)
    speaker_diarization_model: str = "pyannote/speaker-diarization-community-1"
    speaker_diarization_token: str | None = None
    speaker_diarization_device: str = "cpu"
    speaker_diarization_low_volume_retry: bool = True
    voiceprint_enabled: bool = False
    voiceprint_model: str = "pyannote/embedding"
    voiceprint_encryption_key: str | None = None
    voiceprint_match_threshold: float = Field(default=0.75, ge=0.0, le=1.0)
    voiceprint_job_dir: str = "./data/cloud-audio-jobs/voiceprints"
    voiceprint_job_retention_minutes: int = Field(default=15, ge=1, le=60)
    voiceprint_processing_timeout_minutes: int = Field(default=10, ge=1, le=60)
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
    operations_monitor_enabled: bool = False
    operations_alert_line_user_id: str | None = None
    operations_monitor_poll_seconds: float = Field(default=60.0, ge=10.0, le=3_600.0)
    operations_alert_after_seconds: float = Field(default=180.0, ge=30.0, le=86_400.0)
    operations_alert_repeat_seconds: float = Field(default=21_600.0, ge=300.0, le=604_800.0)
    operations_check_timeout_seconds: float = Field(default=10.0, ge=1.0, le=60.0)
    operations_api_readiness_url: str = "http://127.0.0.1:8000/api/v1/readiness"
    operations_vllm_health_url: str = "http://127.0.0.1:8001/health"
    operations_backup_dir: str = "./data/database-backups"
    operations_backup_max_age_hours: float = Field(default=26.0, ge=1.0, le=720.0)
    operations_min_disk_free_gb: float = Field(default=10.0, ge=1.0)
    operations_disk_paths: str = "./data"
    operations_monitor_state_path: str = "./data/operations-monitor-state.json"
    database_backup_dir: str = "./data/database-backups"
    database_backup_time: str = Field(
        default="03:00",
        pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$",
    )
    database_backup_worker_poll_seconds: float = Field(default=300.0, ge=30.0, le=3_600.0)
    database_backup_retention_count: int = Field(default=0, ge=0, le=365)
    database_backup_offsite_enabled: bool = False
    database_backup_age_recipient: str | None = None
    database_backup_s3_bucket: str | None = None
    database_backup_s3_prefix: str = "small-step/database"
    database_backup_s3_endpoint_url: str | None = None
    database_backup_s3_region: str | None = None
    database_backup_s3_sse: Literal["AES256", "aws:kms", "none"] = "AES256"
    database_backup_s3_kms_key_id: str | None = None

    @model_validator(mode="after")
    def reject_unsafe_production_configuration(self) -> "Settings":
        """Keep local defaults from accidentally becoming a public deployment."""

        if self.worker_heartbeat_stale_seconds <= self.worker_heartbeat_interval_seconds:
            raise ValueError(
                "WORKER_HEARTBEAT_STALE_SECONDS must be greater than WORKER_HEARTBEAT_INTERVAL_SECONDS"
            )
        if self.database_backup_offsite_enabled:
            if not self.database_backup_age_recipient or not self.database_backup_s3_bucket:
                raise ValueError(
                    "Off-site backup requires DATABASE_BACKUP_AGE_RECIPIENT and "
                    "DATABASE_BACKUP_S3_BUCKET"
                )
            if self.database_backup_s3_endpoint_url:
                endpoint_url = urlparse(self.database_backup_s3_endpoint_url)
                if endpoint_url.scheme != "https" or not endpoint_url.netloc:
                    raise ValueError("Off-site backup S3 endpoint must use HTTPS")
            if (
                self.database_backup_s3_sse == "aws:kms"
                and not self.database_backup_s3_kms_key_id
            ):
                raise ValueError(
                    "aws:kms backup encryption requires DATABASE_BACKUP_S3_KMS_KEY_ID"
                )
        if self.voiceprint_enabled:
            if not self.cloud_audio_enabled:
                raise ValueError("VOICEPRINT_ENABLED requires CLOUD_AUDIO_ENABLED")
            if not self.voiceprint_encryption_key:
                raise ValueError("VOICEPRINT_ENABLED requires VOICEPRINT_ENCRYPTION_KEY")
            try:
                decoded_key = base64.b64decode(
                    self.voiceprint_encryption_key,
                    altchars=b"-_",
                    validate=True,
                )
            except (ValueError, binascii.Error) as error:
                raise ValueError(
                    "VOICEPRINT_ENCRYPTION_KEY must be a valid Fernet key"
                ) from error
            if len(decoded_key) != 32:
                raise ValueError("VOICEPRINT_ENCRYPTION_KEY must be a valid Fernet key")
            if not self.speaker_diarization_token:
                raise ValueError("VOICEPRINT_ENABLED requires SPEAKER_DIARIZATION_TOKEN")
        if self.app_env != "production":
            return self

        if self.recorder_enabled:
            if not self.cloud_audio_enabled:
                raise ValueError("RECORDER_ENABLED requires CLOUD_AUDIO_ENABLED in production")
            if not self.recorder_worker_heartbeat_required:
                raise ValueError("Production recorder requires RECORDER_WORKER_HEARTBEAT_REQUIRED=true")

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
