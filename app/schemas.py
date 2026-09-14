from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import AuditEventAction, CloudAudioJobStatus, NotificationStatus, RecordCategory, RecordStatus, TeacherRole


class APIModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class SchoolCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    timezone: str = Field(default="Asia/Tokyo", min_length=1, max_length=64)
    digest_time: str | None = Field(default=None, pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    initial_admin_name: str | None = Field(default=None, min_length=1, max_length=120)


class SchoolDigestTimeUpdate(BaseModel):
    """Set the default daily delivery time for future growth records."""

    digest_time: str = Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")


class SchoolRead(APIModel):
    id: UUID
    name: str
    timezone: str
    digest_time: str
    created_at: datetime


class TeacherCreate(BaseModel):
    school_id: UUID
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(max_length=320)
    role: TeacherRole = TeacherRole.teacher


class TeacherRoleUpdate(BaseModel):
    """Change a teacher between standard-teacher and school-admin access."""

    role: TeacherRole


class TeacherRead(APIModel):
    id: UUID
    school_id: UUID
    name: str
    email: str | None
    role: TeacherRole
    is_auth_linked: bool
    is_active: bool
    disabled_at: datetime | None
    created_at: datetime

    @field_validator("disabled_at", "created_at")
    @classmethod
    def normalise_datetime(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


class AuthClientConfig(BaseModel):
    """Public auth settings required by the local teacher web client."""

    auth_mode: Literal["development", "supabase"]
    supabase_url: str | None = None
    supabase_publishable_key: str | None = None


class RuntimeReadinessRead(BaseModel):
    """Public, secret-free deployment readiness summary."""

    status: Literal["ready", "not_ready"]
    database_ready: bool
    database_migration_current: bool
    cloud_audio_enabled: bool
    cloud_audio_job_storage_ready: bool | None
    cloud_audio_llm_configured: bool | None
    cloud_audio_worker_ready: bool | None
    line_delivery_configured: bool
    line_delivery_worker_ready: bool | None


class AuthBootstrapTeacherCreate(BaseModel):
    school_id: UUID
    name: str = Field(min_length=1, max_length=120)


class EdgeDeviceCreate(BaseModel):
    school_id: UUID
    teacher_id: UUID
    name: str = Field(min_length=1, max_length=120)


class EdgeDeviceRead(APIModel):
    id: UUID
    school_id: UUID
    teacher_id: UUID
    name: str
    is_active: bool
    last_seen_at: datetime | None
    created_at: datetime


class EdgeDeviceCredential(EdgeDeviceRead):
    """The key is returned only when a device is created or rotated."""

    api_key: str


class VoiceConsentCreate(BaseModel):
    """An explicit acknowledgement before local voiceprint enrollment is enabled."""

    accepts_voiceprint_enrollment: Literal[True]
    retention_days: int = Field(default=30, ge=1, le=365)


class VoiceConsentRead(APIModel):
    id: UUID
    school_id: UUID
    teacher_id: UUID
    purpose: str
    policy_version: str
    retention_days: int
    consented_at: datetime
    expires_at: datetime
    revoked_at: datetime | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ChildCreate(BaseModel):
    school_id: UUID
    display_name: str = Field(min_length=1, max_length=120)
    guardian_line_user_id: str | None = Field(default=None, max_length=255)


class ChildUpdate(BaseModel):
    display_name: str = Field(min_length=1, max_length=120)


class ChildRead(APIModel):
    id: UUID
    school_id: UUID
    display_name: str
    guardian_line_user_id: str | None
    is_active: bool
    archived_at: datetime | None
    created_at: datetime

    @field_validator("archived_at", "created_at")
    @classmethod
    def normalise_datetime_to_utc(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


class LineLinkInvitationCreate(BaseModel):
    child_id: UUID
    expires_in_minutes: int = Field(default=30, ge=5, le=1_440)


class LineLinkInvitationRead(APIModel):
    id: UUID
    school_id: UUID
    child_id: UUID
    expires_at: datetime
    used_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime


class LineLinkInvitationCredential(LineLinkInvitationRead):
    """The one-time code is returned only when a teacher creates it."""

    invite_code: str


class GuardianArchiveLinkCreate(BaseModel):
    child_id: UUID
    expires_in_hours: int | None = Field(default=None, ge=1, le=720)


class GuardianArchiveLinkRead(APIModel):
    id: UUID
    school_id: UUID
    child_id: UUID
    expires_at: datetime
    revoked_at: datetime | None
    created_at: datetime


class GuardianArchiveLinkCredential(GuardianArchiveLinkRead):
    """The passwordless archive URL is returned only when a teacher issues it."""

    archive_url: str


class GuardianArchiveNotificationRead(BaseModel):
    delivered_at: datetime
    category: RecordCategory
    summary: str
    conversation_prompt: str | None


class GuardianArchiveRead(BaseModel):
    child_display_name: str
    expires_at: datetime
    notifications: list[GuardianArchiveNotificationRead]


class AuditEventRead(APIModel):
    """Admin-facing operational history without child details or internal IDs."""

    action: AuditEventAction
    target_type: str
    actor_display_name: str | None
    created_at: datetime


class RecordCreate(BaseModel):
    """Input from the trusted edge-AI pipeline; never send raw audio here."""

    school_id: UUID
    teacher_id: UUID
    child_id: UUID | None = None
    category: RecordCategory
    source_event_id: str | None = Field(default=None, max_length=128)
    confidence: float = Field(ge=0, le=1)
    occurred_at: datetime
    summary: str = Field(min_length=1, max_length=4000)
    conversation_prompt: str | None = Field(default=None, max_length=4000)
    anonymized_context: str | None = Field(default=None, max_length=4000)


class ManualRecordCreate(BaseModel):
    """A teacher's hand-entered candidate, kept in the same review flow as audio."""

    school_id: UUID
    teacher_id: UUID | None = None
    child_id: UUID
    category: RecordCategory
    occurred_at: datetime
    summary: str = Field(min_length=1, max_length=4000)
    conversation_prompt: str | None = Field(default=None, max_length=4000)


class EdgeRecordCreate(BaseModel):
    """An anonymized candidate sent by a registered edge device.

    Device and school IDs are intentionally absent: they are derived from the
    API key, and unrecognised fields (including raw-audio fields) are rejected.
    """

    model_config = ConfigDict(extra="forbid")

    child_id: UUID | None = None
    category: RecordCategory
    source_event_id: str | None = Field(default=None, max_length=128)
    confidence: float = Field(ge=0, le=1)
    occurred_at: datetime
    summary: str = Field(min_length=1, max_length=4000)
    conversation_prompt: str | None = Field(default=None, max_length=4000)
    anonymized_context: str | None = Field(default=None, max_length=4000)


class CloudAudioJobRead(APIModel):
    """Safe job metadata. Raw-audio locations and filenames are never exposed."""

    id: UUID
    school_id: UUID
    teacher_id: UUID
    device_id: UUID
    child_id: UUID | None
    status: CloudAudioJobStatus
    attempts: int
    detected_speaker_count: int | None
    used_low_volume_retry: bool | None
    candidate_category: RecordCategory | None
    record_id: UUID | None
    queued_at: datetime
    processing_started_at: datetime | None
    completed_at: datetime | None
    expires_at: datetime
    created_at: datetime
    updated_at: datetime


class RecordReview(BaseModel):
    child_id: UUID | None = None
    summary: str | None = Field(default=None, min_length=1, max_length=4000)
    conversation_prompt: str | None = Field(default=None, min_length=1, max_length=4000)
    scheduled_for: datetime | None = None


class RecordRead(APIModel):
    id: UUID
    school_id: UUID
    teacher_id: UUID
    child_id: UUID | None
    category: RecordCategory
    status: RecordStatus
    source_event_id: str | None
    confidence: float
    occurred_at: datetime
    summary: str
    conversation_prompt: str | None
    anonymized_context: str | None
    reviewed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    @field_validator("occurred_at", "reviewed_at", "created_at", "updated_at")
    @classmethod
    def normalise_datetime_to_utc(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


class NotificationRead(APIModel):
    id: UUID
    record_id: UUID
    channel: str
    recipient_line_user_id: str | None
    scheduled_for: datetime
    status: NotificationStatus
    provider_message_id: str | None
    delivery_attempts: int
    last_attempt_at: datetime | None
    last_failure_kind: str | None
    sent_at: datetime | None
    created_at: datetime

    @field_validator("scheduled_for", "last_attempt_at", "sent_at", "created_at")
    @classmethod
    def normalise_datetime_to_utc(cls, value: datetime | None) -> datetime | None:
        """SQLite omits timezone data, while API clients always receive UTC."""

        if value is None:
            return None
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


class NotificationOverviewRead(APIModel):
    """Teacher-facing notification status without exposing LINE identifiers."""

    id: UUID
    record_id: UUID
    channel: str
    scheduled_for: datetime
    status: NotificationStatus
    delivery_attempts: int
    last_attempt_at: datetime | None
    last_failure_kind: str | None
    sent_at: datetime | None
    created_at: datetime
    child_id: UUID | None
    child_display_name: str | None
    category: RecordCategory
    summary: str
    notion_synced_at: datetime | None
    notion_page_url: str | None


class NotificationSent(BaseModel):

    provider_message_id: str | None = Field(default=None, max_length=255)


class NotificationReschedule(BaseModel):
    scheduled_for: datetime


class NotionSyncRead(APIModel):
    id: UUID
    record_id: UUID
    notion_page_id: str
    notion_page_url: str | None
    synced_at: datetime
    created_at: datetime
