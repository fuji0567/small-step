"""Add independent /rec recorder session metadata and segment storage.

Revision ID: 0022_recording_sessions
Revises: 0021_teacher_voiceprints
Create Date: 2026-09-15
"""

import sqlalchemy as sa
from alembic import op


revision = "0022_recording_sessions"
down_revision = "0021_teacher_voiceprints"
branch_labels = None
depends_on = None


recording_session_status = sa.Enum(
    "draft",
    "queued",
    "processing",
    "completed",
    "failed",
    "discarded",
    "expired",
    name="recordingsessionstatus",
)


def _protect_from_supabase_data_api(table_name: str) -> None:
    """Apply the repository's deny-by-default Data API convention on Postgres."""

    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    roles = tuple(
        bind.execute(
            sa.text(
                "SELECT rolname FROM pg_roles "
                "WHERE rolname IN ('anon', 'authenticated', 'service_role')"
            )
        ).scalars()
    )
    if not roles:
        return
    op.execute(f'ALTER TABLE public."{table_name}" ENABLE ROW LEVEL SECURITY')
    for role in roles:
        op.execute(f'REVOKE ALL PRIVILEGES ON TABLE public."{table_name}" FROM "{role}"')


def upgrade() -> None:
    # Keep this flag on the eventual Record rather than on the session: one
    # candidate record may be assembled from several independently processed
    # segments.
    op.add_column(
        "records",
        sa.Column(
            "audio_processing_incomplete",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.create_table(
        "recording_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("school_id", sa.String(length=36), nullable=False),
        sa.Column("teacher_id", sa.String(length=36), nullable=False),
        sa.Column("client_session_id", sa.String(length=36), nullable=False),
        sa.Column("status", recording_session_status, nullable=False),
        sa.Column("record_id", sa.String(length=36), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["record_id"], ["records.id"]),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"]),
        sa.ForeignKeyConstraint(["teacher_id"], ["teachers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "teacher_id", "client_session_id", name="uq_recording_session_owner_client"
        ),
    )
    for index_name, columns in (
        ("ix_recording_sessions_school_id", ["school_id"]),
        ("ix_recording_sessions_teacher_id", ["teacher_id"]),
        ("ix_recording_sessions_status", ["status"]),
        ("ix_recording_sessions_record_id", ["record_id"]),
        ("ix_recording_sessions_expires_at", ["expires_at"]),
        ("ix_recording_sessions_updated_at", ["updated_at"]),
    ):
        op.create_index(index_name, "recording_sessions", columns)

    op.create_table(
        "recording_segments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("media_type", sa.String(length=128), nullable=False),
        sa.Column("storage_key", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["recording_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "session_id", "sequence", name="uq_recording_segment_session_sequence"
        ),
        sa.UniqueConstraint("storage_key"),
    )
    op.create_index("ix_recording_segments_session_id", "recording_segments", ["session_id"])
    op.create_index("ix_recording_segments_sequence", "recording_segments", ["sequence"])
    op.create_index("ix_recording_segments_sha256", "recording_segments", ["sha256"])

    _protect_from_supabase_data_api("recording_sessions")
    _protect_from_supabase_data_api("recording_segments")


def downgrade() -> None:
    op.drop_index("ix_recording_segments_sha256", table_name="recording_segments")
    op.drop_index("ix_recording_segments_sequence", table_name="recording_segments")
    op.drop_index("ix_recording_segments_session_id", table_name="recording_segments")
    op.drop_table("recording_segments")
    for index_name in (
        "ix_recording_sessions_updated_at",
        "ix_recording_sessions_expires_at",
        "ix_recording_sessions_record_id",
        "ix_recording_sessions_status",
        "ix_recording_sessions_teacher_id",
        "ix_recording_sessions_school_id",
    ):
        op.drop_index(index_name, table_name="recording_sessions")
    op.drop_table("recording_sessions")
    op.drop_column("records", "audio_processing_incomplete")
    if op.get_bind().dialect.name == "postgresql":
        recording_session_status.drop(op.get_bind(), checkfirst=True)
