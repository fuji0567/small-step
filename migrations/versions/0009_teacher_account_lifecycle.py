"""Support safe teacher account disablement and restoration.

Revision ID: 0009_teacher_account_lifecycle
Revises: 0008_child_restoration
Create Date: 2026-08-30
"""

from alembic import op
import sqlalchemy as sa


revision = "0009_teacher_account_lifecycle"
down_revision = "0008_child_restoration"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("teachers", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("teachers", sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_teachers_is_active", "teachers", ["is_active"], unique=False)
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TYPE auditeventaction ADD VALUE IF NOT EXISTS 'teacher_disabled'")
        op.execute("ALTER TYPE auditeventaction ADD VALUE IF NOT EXISTS 'teacher_restored'")


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        raise RuntimeError("teacher lifecycle audit actions cannot be removed safely")
    op.drop_index("ix_teachers_is_active", table_name="teachers")
    op.drop_column("teachers", "disabled_at")
    op.drop_column("teachers", "is_active")
