"""Record safe teacher administrator handovers in the audit trail.

Revision ID: 0010_teacher_role_handover
Revises: 0009_teacher_account_lifecycle
Create Date: 2026-08-31
"""

from alembic import op


revision = "0010_teacher_role_handover"
down_revision = "0009_teacher_account_lifecycle"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TYPE auditeventaction ADD VALUE IF NOT EXISTS 'teacher_role_changed'")


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        raise RuntimeError("teacher role audit actions cannot be removed safely")
