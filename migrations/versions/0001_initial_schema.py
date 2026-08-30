"""Create the initial Small Step application schema.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-08-30
"""

from alembic import op
import sqlalchemy as sa


revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


teacher_role = sa.Enum("school_admin", "teacher", name="teacherrole")
cloud_audio_job_status = sa.Enum("queued", "processing", "completed", "failed", "expired", name="cloudaudiojobstatus")
audit_event_action = sa.Enum(
    "line_link_invitation_issued",
    "guardian_line_linked",
    "guardian_line_unlinked",
    "guardian_archive_issued",
    "guardian_archive_revoked",
    "record_approved",
    "record_rejected",
    "notification_retry_scheduled",
    "notion_synced",
    "edge_device_created",
    "edge_device_key_rotated",
    "edge_device_disabled",
    name="auditeventaction",
)
record_category = sa.Enum("growth", "injury", name="recordcategory")
record_status = sa.Enum("pending_review", "approved", "rejected", "dispatched", name="recordstatus")
notification_status = sa.Enum("pending", "sent", "failed", name="notificationstatus")


def upgrade() -> None:
    op.create_table(
        "schools",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_schools_name", "schools", ["name"], unique=True)

    op.create_table(
        "teachers",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("school_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("auth_user_id", sa.String(length=36), nullable=True),
        sa.Column("role", teacher_role, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_teachers_auth_user_id", "teachers", ["auth_user_id"], unique=True)
    op.create_index("ix_teachers_school_id", "teachers", ["school_id"], unique=False)

    op.create_table(
        "children",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("school_id", sa.String(length=36), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("guardian_line_user_id", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_children_school_id", "children", ["school_id"], unique=False)

    op.create_table(
        "edge_devices",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("school_id", sa.String(length=36), nullable=False),
        sa.Column("teacher_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("api_key_hash", sa.String(length=64), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"]),
        sa.ForeignKeyConstraint(["teacher_id"], ["teachers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("school_id", "name", name="uq_edge_device_school_name"),
    )
    op.create_index("ix_edge_devices_api_key_hash", "edge_devices", ["api_key_hash"], unique=True)
    op.create_index("ix_edge_devices_school_id", "edge_devices", ["school_id"], unique=False)
    op.create_index("ix_edge_devices_teacher_id", "edge_devices", ["teacher_id"], unique=False)

    op.create_table(
        "voice_enrollment_consents",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("school_id", sa.String(length=36), nullable=False),
        sa.Column("teacher_id", sa.String(length=36), nullable=False),
        sa.Column("purpose", sa.String(length=120), nullable=False),
        sa.Column("policy_version", sa.String(length=32), nullable=False),
        sa.Column("retention_days", sa.Integer(), nullable=False),
        sa.Column("consented_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"]),
        sa.ForeignKeyConstraint(["teacher_id"], ["teachers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("teacher_id", name="uq_voice_enrollment_consent_teacher"),
    )
    op.create_index("ix_voice_enrollment_consents_expires_at", "voice_enrollment_consents", ["expires_at"])
    op.create_index("ix_voice_enrollment_consents_school_id", "voice_enrollment_consents", ["school_id"])
    op.create_index("ix_voice_enrollment_consents_teacher_id", "voice_enrollment_consents", ["teacher_id"])

    op.create_table(
        "line_link_invitations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("school_id", sa.String(length=36), nullable=False),
        sa.Column("child_id", sa.String(length=36), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["child_id"], ["children.id"]),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_line_link_invitations_child_id", "line_link_invitations", ["child_id"])
    op.create_index("ix_line_link_invitations_code_hash", "line_link_invitations", ["code_hash"], unique=True)
    op.create_index("ix_line_link_invitations_expires_at", "line_link_invitations", ["expires_at"])
    op.create_index("ix_line_link_invitations_school_id", "line_link_invitations", ["school_id"])

    op.create_table(
        "guardian_archive_links",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("school_id", sa.String(length=36), nullable=False),
        sa.Column("child_id", sa.String(length=36), nullable=False),
        sa.Column("created_by_teacher_id", sa.String(length=36), nullable=True),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["child_id"], ["children.id"]),
        sa.ForeignKeyConstraint(["created_by_teacher_id"], ["teachers.id"]),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_guardian_archive_links_child_id", "guardian_archive_links", ["child_id"])
    op.create_index("ix_guardian_archive_links_created_by_teacher_id", "guardian_archive_links", ["created_by_teacher_id"])
    op.create_index("ix_guardian_archive_links_expires_at", "guardian_archive_links", ["expires_at"])
    op.create_index("ix_guardian_archive_links_school_id", "guardian_archive_links", ["school_id"])
    op.create_index("ix_guardian_archive_links_token_hash", "guardian_archive_links", ["token_hash"], unique=True)

    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("school_id", sa.String(length=36), nullable=False),
        sa.Column("actor_teacher_id", sa.String(length=36), nullable=True),
        sa.Column("action", audit_event_action, nullable=False),
        sa.Column("target_type", sa.String(length=48), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_teacher_id"], ["teachers.id"]),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_events_action", "audit_events", ["action"])
    op.create_index("ix_audit_events_actor_teacher_id", "audit_events", ["actor_teacher_id"])
    op.create_index("ix_audit_events_created_at", "audit_events", ["created_at"])
    op.create_index("ix_audit_events_school_id", "audit_events", ["school_id"])

    op.create_table(
        "records",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("school_id", sa.String(length=36), nullable=False),
        sa.Column("teacher_id", sa.String(length=36), nullable=False),
        sa.Column("child_id", sa.String(length=36), nullable=True),
        sa.Column("category", record_category, nullable=False),
        sa.Column("status", record_status, nullable=False),
        sa.Column("source_event_id", sa.String(length=128), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("conversation_prompt", sa.Text(), nullable=True),
        sa.Column("anonymized_context", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["child_id"], ["children.id"]),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"]),
        sa.ForeignKeyConstraint(["teacher_id"], ["teachers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("school_id", "source_event_id", name="uq_record_source_event"),
    )
    op.create_index("ix_records_category", "records", ["category"])
    op.create_index("ix_records_child_id", "records", ["child_id"])
    op.create_index("ix_records_occurred_at", "records", ["occurred_at"])
    op.create_index("ix_records_school_id", "records", ["school_id"])
    op.create_index("ix_records_status", "records", ["status"])
    op.create_index("ix_records_teacher_id", "records", ["teacher_id"])

    op.create_table(
        "cloud_audio_jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("school_id", sa.String(length=36), nullable=False),
        sa.Column("teacher_id", sa.String(length=36), nullable=False),
        sa.Column("device_id", sa.String(length=36), nullable=False),
        sa.Column("child_id", sa.String(length=36), nullable=True),
        sa.Column("storage_key", sa.String(length=80), nullable=False),
        sa.Column("status", cloud_audio_job_status, nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("record_id", sa.String(length=36), nullable=True),
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processing_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["child_id"], ["children.id"]),
        sa.ForeignKeyConstraint(["device_id"], ["edge_devices.id"]),
        sa.ForeignKeyConstraint(["record_id"], ["records.id"]),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"]),
        sa.ForeignKeyConstraint(["teacher_id"], ["teachers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key"),
    )
    op.create_index("ix_cloud_audio_jobs_child_id", "cloud_audio_jobs", ["child_id"])
    op.create_index("ix_cloud_audio_jobs_device_id", "cloud_audio_jobs", ["device_id"])
    op.create_index("ix_cloud_audio_jobs_expires_at", "cloud_audio_jobs", ["expires_at"])
    op.create_index("ix_cloud_audio_jobs_queued_at", "cloud_audio_jobs", ["queued_at"])
    op.create_index("ix_cloud_audio_jobs_record_id", "cloud_audio_jobs", ["record_id"])
    op.create_index("ix_cloud_audio_jobs_school_id", "cloud_audio_jobs", ["school_id"])
    op.create_index("ix_cloud_audio_jobs_status", "cloud_audio_jobs", ["status"])
    op.create_index("ix_cloud_audio_jobs_teacher_id", "cloud_audio_jobs", ["teacher_id"])

    op.create_table(
        "notifications",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("record_id", sa.String(length=36), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("recipient_line_user_id", sa.String(length=255), nullable=True),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", notification_status, nullable=False),
        sa.Column("provider_message_id", sa.String(length=255), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["record_id"], ["records.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notifications_record_id", "notifications", ["record_id"], unique=True)
    op.create_index("ix_notifications_scheduled_for", "notifications", ["scheduled_for"])
    op.create_index("ix_notifications_status", "notifications", ["status"])

    op.create_table(
        "notion_syncs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("record_id", sa.String(length=36), nullable=False),
        sa.Column("notion_page_id", sa.String(length=255), nullable=False),
        sa.Column("notion_page_url", sa.String(length=2048), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["record_id"], ["records.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("notion_page_id"),
    )
    op.create_index("ix_notion_syncs_record_id", "notion_syncs", ["record_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_notion_syncs_record_id", table_name="notion_syncs")
    op.drop_table("notion_syncs")
    op.drop_index("ix_notifications_status", table_name="notifications")
    op.drop_index("ix_notifications_scheduled_for", table_name="notifications")
    op.drop_index("ix_notifications_record_id", table_name="notifications")
    op.drop_table("notifications")
    for index_name in (
        "ix_cloud_audio_jobs_teacher_id",
        "ix_cloud_audio_jobs_status",
        "ix_cloud_audio_jobs_school_id",
        "ix_cloud_audio_jobs_record_id",
        "ix_cloud_audio_jobs_queued_at",
        "ix_cloud_audio_jobs_expires_at",
        "ix_cloud_audio_jobs_device_id",
        "ix_cloud_audio_jobs_child_id",
    ):
        op.drop_index(index_name, table_name="cloud_audio_jobs")
    op.drop_table("cloud_audio_jobs")
    for index_name in (
        "ix_records_teacher_id",
        "ix_records_status",
        "ix_records_school_id",
        "ix_records_occurred_at",
        "ix_records_child_id",
        "ix_records_category",
    ):
        op.drop_index(index_name, table_name="records")
    op.drop_table("records")
    for index_name in (
        "ix_audit_events_school_id",
        "ix_audit_events_created_at",
        "ix_audit_events_actor_teacher_id",
        "ix_audit_events_action",
    ):
        op.drop_index(index_name, table_name="audit_events")
    op.drop_table("audit_events")
    for index_name in (
        "ix_guardian_archive_links_token_hash",
        "ix_guardian_archive_links_school_id",
        "ix_guardian_archive_links_expires_at",
        "ix_guardian_archive_links_created_by_teacher_id",
        "ix_guardian_archive_links_child_id",
    ):
        op.drop_index(index_name, table_name="guardian_archive_links")
    op.drop_table("guardian_archive_links")
    for index_name in (
        "ix_line_link_invitations_school_id",
        "ix_line_link_invitations_expires_at",
        "ix_line_link_invitations_code_hash",
        "ix_line_link_invitations_child_id",
    ):
        op.drop_index(index_name, table_name="line_link_invitations")
    op.drop_table("line_link_invitations")
    for index_name in (
        "ix_voice_enrollment_consents_teacher_id",
        "ix_voice_enrollment_consents_school_id",
        "ix_voice_enrollment_consents_expires_at",
    ):
        op.drop_index(index_name, table_name="voice_enrollment_consents")
    op.drop_table("voice_enrollment_consents")
    for index_name in (
        "ix_edge_devices_teacher_id",
        "ix_edge_devices_school_id",
        "ix_edge_devices_api_key_hash",
    ):
        op.drop_index(index_name, table_name="edge_devices")
    op.drop_table("edge_devices")
    op.drop_index("ix_children_school_id", table_name="children")
    op.drop_table("children")
    op.drop_index("ix_teachers_school_id", table_name="teachers")
    op.drop_index("ix_teachers_auth_user_id", table_name="teachers")
    op.drop_table("teachers")
    op.drop_index("ix_schools_name", table_name="schools")
    op.drop_table("schools")

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        notification_status.drop(bind, checkfirst=True)
        record_status.drop(bind, checkfirst=True)
        record_category.drop(bind, checkfirst=True)
        audit_event_action.drop(bind, checkfirst=True)
        cloud_audio_job_status.drop(bind, checkfirst=True)
        teacher_role.drop(bind, checkfirst=True)
