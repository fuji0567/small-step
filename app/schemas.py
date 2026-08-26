from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models import NotificationStatus, RecordCategory, RecordStatus, TeacherRole


class APIModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class SchoolCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    timezone: str = Field(default="Asia/Tokyo", min_length=1, max_length=64)
    initial_admin_name: str | None = Field(default=None, min_length=1, max_length=120)


class SchoolRead(APIModel):
    id: UUID
    name: str
    timezone: str
    created_at: datetime


class TeacherCreate(BaseModel):
    school_id: UUID
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(max_length=320)
    role: TeacherRole = TeacherRole.teacher


class TeacherRead(APIModel):
    id: UUID
    school_id: UUID
    name: str
    email: str | None
    role: TeacherRole
    created_at: datetime


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


class ChildCreate(BaseModel):
    school_id: UUID
    display_name: str = Field(min_length=1, max_length=120)
    guardian_line_user_id: str | None = Field(default=None, max_length=255)


class ChildRead(APIModel):
    id: UUID
    school_id: UUID
    display_name: str
    guardian_line_user_id: str | None
    created_at: datetime


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


class NotificationRead(APIModel):
    id: UUID
    record_id: UUID
    channel: str
    recipient_line_user_id: str | None
    scheduled_for: datetime
    status: NotificationStatus
    provider_message_id: str | None
    sent_at: datetime | None
    created_at: datetime


class NotificationOverviewRead(APIModel):
    """Teacher-facing notification status without exposing LINE identifiers."""

    id: UUID
    record_id: UUID
    channel: str
    scheduled_for: datetime
    status: NotificationStatus
    sent_at: datetime | None
    created_at: datetime
    child_id: UUID | None
    child_display_name: str | None
    category: RecordCategory
    summary: str


class NotificationSent(BaseModel):

    provider_message_id: str | None = Field(default=None, max_length=255)
class NotionSyncRead(APIModel):
    id: UUID
    record_id: UUID
    notion_page_id: str
    notion_page_url: str | None
    synced_at: datetime
    created_at: datetime
