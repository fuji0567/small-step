import enum
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, String, Text, UniqueConstraint
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
    sent = "sent"
    failed = "failed"


class TeacherRole(str, enum.Enum):
    school_admin = "school_admin"
    teacher = "teacher"


class School(Base):
    __tablename__ = "schools"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_text)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Tokyo")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class Teacher(Base):
    __tablename__ = "teachers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_text)
    school_id: Mapped[str] = mapped_column(ForeignKey("schools.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str | None] = mapped_column(String(320), unique=True, nullable=True)
    auth_user_id: Mapped[str | None] = mapped_column(String(36), unique=True, nullable=True, index=True)
    role: Mapped[TeacherRole] = mapped_column(Enum(TeacherRole), default=TeacherRole.teacher)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


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


class Child(Base):
    __tablename__ = "children"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_text)
    school_id: Mapped[str] = mapped_column(ForeignKey("schools.id"), index=True)
    display_name: Mapped[str] = mapped_column(String(120))
    guardian_line_user_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
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
