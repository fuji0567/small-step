"""Support quality-checked multi-sample voiceprint enrollment.

Revision ID: 0022_voiceprint_multi_sample
Revises: 0021_teacher_voiceprints
Create Date: 2026-09-16
"""

import sqlalchemy as sa
from alembic import op


revision = "0022_voiceprint_multi_sample"
down_revision = "0021_teacher_voiceprints"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "teacher_voiceprints",
        sa.Column("sample_count", sa.Integer(), server_default="1", nullable=False),
    )
    op.add_column(
        "voiceprint_jobs",
        sa.Column("sample_storage_keys", sa.JSON(), nullable=True),
    )
    op.add_column(
        "voiceprint_jobs",
        sa.Column("quality_issue", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "voiceprint_jobs",
        sa.Column("quality_sample_index", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("voiceprint_jobs", "quality_sample_index")
    op.drop_column("voiceprint_jobs", "quality_issue")
    op.drop_column("voiceprint_jobs", "sample_storage_keys")
    op.drop_column("teacher_voiceprints", "sample_count")
