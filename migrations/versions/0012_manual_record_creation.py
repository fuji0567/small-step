"""Add an audit action for teacher hand-entered record candidates.

Revision ID: 0012_manual_record_creation
Revises: 0011_school_digest_time
Create Date: 2026-08-31
"""

from alembic import op


revision = "0012_manual_record_creation"
down_revision = "0011_school_digest_time"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TYPE auditeventaction ADD VALUE IF NOT EXISTS 'manual_record_created'")


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        raise RuntimeError("manual record audit actions cannot be removed safely")
