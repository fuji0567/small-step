import enum
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def uuid_text() -> str:
    return str(uuid4())


class Base(DeclarativeBase):
    pass


class RecordCategory(str, enum.Enum):
    growth = "growth"
    injury = "injury"


class RecordStatus(str, enum.Enum):
    pending_review = "pending_review"
    approved = "approved"
    rejected = "rejected"
    dispatched = "dispatched"


class NotificationStatus(str, enum.Enum):
    pending = "pending"
    waiting_guardian_link = "waiting_guardian_link"
    sent = "sent"
    failed = "failed"
    cancelled = "cancelled"


class TeacherRole(str, enum.Enum):
    school_admin = "school_admin"
    teacher = "teacher"


class CloudAudioJobStatus(str, enum.Enum):
    queued = "queued"
    processing = "processing"
    completed = "completed"
    failed = "failed"
    expired = "expired"


class WorkerHeartbeat(Base):
    """A data-free liveness marker written by a long-running worker."""

    __tablename__ = "worker_heartbeats"

    worker_name: Mapped[str] = mapped_column(String(64), primary_key=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class AuditEventAction(str, enum.Enum):
    """Safe operational events that never contain audio, transcripts, or secrets."""

    line_link_invitation_issued = "line_link_invitation_issued"
    guardian_line_linked = "guardian_line_linked"
    guardian_line_unlinked = "guardian_line_unlinked"
    guardian_archive_issued = "guardian_archive_issued"
    guardian_archive_revoked = "guardian_archive_revoked"
    record_approved = "record_approved"
    record_rejected = "record_rejected"
    notification_retry_scheduled = "notification_retry_scheduled"
    notification_cancelled = "notification_cancelled"
    notification_rescheduled = "notification_rescheduled"
    child_updated = "child_updated"
    child_archived = "child_archived"
    child_restored = "child_restored"
    teacher_disabled = "teacher_disabled"
    teacher_restored = "teacher_restored"
    teacher_role_changed = "teacher_role_changed"
    school_digest_time_changed = "school_digest_time_changed"
    manual_record_created = "manual_record_created"
    record_history_exported = "record_history_exported"
    audit_history_exported = "audit_history_exported"
    notion_synced = "notion_synced"
    edge_device_created = "edge_device_created"
    edge_device_key_rotated = "edge_device_key_rotated"
    edge_device_disabled = "edge_device_disabled"


class School(Base):
    __tablename__ = "schools"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_text)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Tokyo")
    digest_time: Mapped[str] = mapped_column(String(5), default="17:00")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class Teacher(Base):
    __tablename__ = "teachers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_text)
    school_id: Mapped[str] = mapped_column(ForeignKey("schools.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str | None] = mapped_column(String(320), unique=True, nullable=True)
    auth_user_id: Mapped[str | None] = mapped_column(String(36), unique=True, nullable=True, index=True)
    role: Mapped[TeacherRole] = mapped_column(Enum(TeacherRole), default=TeacherRole.teacher)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    @property
    def is_auth_linked(self) -> bool:
        """Expose only whether a teacher has completed Supabase login."""

        return self.auth_user_id is not None


class EdgeDevice(Base):
    """A wearable or on-premise edge processor assigned to one teacher."""

    __tablename__ = "edge_devices"
    __table_args__ = (UniqueConstraint("school_id", "name", name="uq_edge_device_school_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_text)
    school_id: Mapped[str] = mapped_column(ForeignKey("schools.id"), index=True)
    teacher_id: Mapped[str] = mapped_column(ForeignKey("teachers.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    api_key_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class VoiceEnrollmentConsent(Base):
    """A teacher's revocable consent before any local voiceprint enrollment."""

    __tablename__ = "voice_enrollment_consents"
    __table_args__ = (UniqueConstraint("teacher_id", name="uq_voice_enrollment_consent_teacher"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_text)
    school_id: Mapped[str] = mapped_column(ForeignKey("schools.id"), index=True)
    teacher_id: Mapped[str] = mapped_column(ForeignKey("teachers.id"), index=True)
    purpose: Mapped[str] = mapped_column(String(120))
    policy_version: Mapped[str] = mapped_column(String(32))
    retention_days: Mapped[int] = mapped_column(Integer)
    consented_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class CloudAudioJob(Base):
    """A short-lived raw-audio job stored only on the configured GPU worker disk."""

    __tablename__ = "cloud_audio_jobs"
    __table_args__ = (
        UniqueConstraint("device_id", "edge_upload_id", name="uq_cloud_audio_job_device_upload"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_text)
    school_id: Mapped[str] = mapped_column(ForeignKey("schools.id"), index=True)
    teacher_id: Mapped[str] = mapped_column(ForeignKey("teachers.id"), index=True)
    device_id: Mapped[str] = mapped_column(ForeignKey("edge_devices.id"), index=True)
    child_id: Mapped[str | None] = mapped_column(ForeignKey("children.id"), nullable=True, index=True)
    # A random edge-only value prevents duplicate jobs after an uncertain network response.
    edge_upload_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    storage_key: Mapped[str] = mapped_column(String(80), unique=True)
    status: Mapped[CloudAudioJobStatus] = mapped_column(
        Enum(CloudAudioJobStatus), default=CloudAudioJobStatus.queued, index=True
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    claim_token: Mapped[str | None] = mapped_column(String(36), nullable=True)
    record_id: Mapped[str | None] = mapped_column(ForeignKey("records.id"), nullable=True, index=True)
    queued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    processing_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class Child(Base):
    __tablename__ = "children"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_text)
    school_id: Mapped[str] = mapped_column(ForeignKey("schools.id"), index=True)
    display_name: Mapped[str] = mapped_column(String(120))
    guardian_line_user_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class LineLinkInvitation(Base):
    """A short-lived code that lets a guardian bind their LINE account to one child."""

    __tablename__ = "line_link_invitations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_text)
    school_id: Mapped[str] = mapped_column(ForeignKey("schools.id"), index=True)
    child_id: Mapped[str] = mapped_column(ForeignKey("children.id"), index=True)
    code_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class GuardianArchiveLink(Base):
    """A revocable, time-limited guardian link for one child's delivered notices."""

    __tablename__ = "guardian_archive_links"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_text)
    school_id: Mapped[str] = mapped_column(ForeignKey("schools.id"), index=True)
    child_id: Mapped[str] = mapped_column(ForeignKey("children.id"), index=True)
    created_by_teacher_id: Mapped[str | None] = mapped_column(ForeignKey("teachers.id"), nullable=True, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class AuditEvent(Base):
    """Minimal operational history for one school.

    The event deliberately stores neither the action's contents nor secret IDs,
    so the history remains useful without becoming a copy of child or audio data.
    """

    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_text)
    school_id: Mapped[str] = mapped_column(ForeignKey("schools.id"), index=True)
    actor_teacher_id: Mapped[str | None] = mapped_column(ForeignKey("teachers.id"), nullable=True, index=True)
    action: Mapped[AuditEventAction] = mapped_column(Enum(AuditEventAction), index=True)
    target_type: Mapped[str] = mapped_column(String(48))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)


class Record(Base):
    """A processed, privacy-filtered candidate awaiting teacher review or delivery."""

    __tablename__ = "records"
    __table_args__ = (UniqueConstraint("school_id", "source_event_id", name="uq_record_source_event"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_text)
    school_id: Mapped[str] = mapped_column(ForeignKey("schools.id"), index=True)
    teacher_id: Mapped[str] = mapped_column(ForeignKey("teachers.id"), index=True)
    child_id: Mapped[str | None] = mapped_column(ForeignKey("children.id"), nullable=True, index=True)
    category: Mapped[RecordCategory] = mapped_column(Enum(RecordCategory), index=True)
    status: Mapped[RecordStatus] = mapped_column(Enum(RecordStatus), default=RecordStatus.pending_review, index=True)
    source_event_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    confidence: Mapped[float] = mapped_column(Float)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    summary: Mapped[str] = mapped_column(Text)
    conversation_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    anonymized_context: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_text)
    record_id: Mapped[str] = mapped_column(ForeignKey("records.id"), unique=True, index=True)
    channel: Mapped[str] = mapped_column(String(32), default="line")
    recipient_line_user_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[NotificationStatus] = mapped_column(Enum(NotificationStatus), default=NotificationStatus.pending, index=True)
    provider_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    delivery_attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_failure_kind: Mapped[str | None] = mapped_column(String(48), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class NotionSync(Base):
    """One Notion page created for one delivered notification."""

    __tablename__ = "notion_syncs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_text)
    record_id: Mapped[str] = mapped_column(ForeignKey("records.id"), unique=True, index=True)
    notion_page_id: Mapped[str] = mapped_column(String(255), unique=True)
    notion_page_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
