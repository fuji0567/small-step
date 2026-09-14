"""Store encrypted teacher voiceprints and short-lived processing jobs.

Revision ID: 0021_teacher_voiceprints
Revises: 0020_record_reassignment_audit
Create Date: 2026-09-15
"""

import sqlalchemy as sa
from alembic import op


revision = "0021_teacher_voiceprints"
down_revision = "0020_record_reassignment_audit"
branch_labels = None
depends_on = None


voiceprint_job_kind = sa.Enum("enrollment", "verification", name="voiceprintjobkind")
voiceprint_job_status = sa.Enum(
    "queued", "processing", "completed", "failed", "expired", name="voiceprintjobstatus"
)


def _protect_from_supabase_data_api(table_name: str) -> None:
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
    op.create_table(
        "teacher_voiceprints",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("school_id", sa.String(length=36), nullable=False),
        sa.Column("teacher_id", sa.String(length=36), nullable=False),
        sa.Column("encrypted_embedding", sa.Text(), nullable=False),
        sa.Column("embedding_dimension", sa.Integer(), nullable=False),
        sa.Column("model_name", sa.String(length=255), nullable=False),
        sa.Column("enrolled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"]),
        sa.ForeignKeyConstraint(["teacher_id"], ["teachers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("teacher_id", name="uq_teacher_voiceprint_teacher"),
    )
    op.create_index("ix_teacher_voiceprints_school_id", "teacher_voiceprints", ["school_id"])
    op.create_index("ix_teacher_voiceprints_teacher_id", "teacher_voiceprints", ["teacher_id"])
    op.create_index("ix_teacher_voiceprints_expires_at", "teacher_voiceprints", ["expires_at"])

    op.create_table(
        "voiceprint_jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("school_id", sa.String(length=36), nullable=False),
        sa.Column("teacher_id", sa.String(length=36), nullable=False),
        sa.Column("kind", voiceprint_job_kind, nullable=False),
        sa.Column("storage_key", sa.String(length=80), nullable=False),
        sa.Column("status", voiceprint_job_status, nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("claim_token", sa.String(length=36), nullable=True),
        sa.Column("similarity_score", sa.Float(), nullable=True),
        sa.Column("matched", sa.Boolean(), nullable=True),
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processing_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"]),
        sa.ForeignKeyConstraint(["teacher_id"], ["teachers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key"),
    )
    op.create_index("ix_voiceprint_jobs_school_id", "voiceprint_jobs", ["school_id"])
    op.create_index("ix_voiceprint_jobs_teacher_id", "voiceprint_jobs", ["teacher_id"])
    op.create_index("ix_voiceprint_jobs_kind", "voiceprint_jobs", ["kind"])
    op.create_index("ix_voiceprint_jobs_status", "voiceprint_jobs", ["status"])
    op.create_index("ix_voiceprint_jobs_queued_at", "voiceprint_jobs", ["queued_at"])
    op.create_index("ix_voiceprint_jobs_expires_at", "voiceprint_jobs", ["expires_at"])

    _protect_from_supabase_data_api("teacher_voiceprints")
    _protect_from_supabase_data_api("voiceprint_jobs")


def downgrade() -> None:
    op.drop_table("voiceprint_jobs")
    op.drop_table("teacher_voiceprints")
    if op.get_bind().dialect.name == "postgresql":
        voiceprint_job_status.drop(op.get_bind(), checkfirst=True)
        voiceprint_job_kind.drop(op.get_bind(), checkfirst=True)
