"""Store the daily growth-record delivery time for each school.

Revision ID: 0011_school_digest_time
Revises: 0010_teacher_role_handover
Create Date: 2026-08-31
"""

from alembic import op
import sqlalchemy as sa


revision = "0011_school_digest_time"
down_revision = "0010_teacher_role_handover"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "schools",
        sa.Column("digest_time", sa.String(length=5), nullable=False, server_default=sa.text("'17:00'")),
    )
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TYPE auditeventaction ADD VALUE IF NOT EXISTS 'school_digest_time_changed'")


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        raise RuntimeError("school delivery-time audit actions cannot be removed safely")
    op.drop_column("schools", "digest_time")
