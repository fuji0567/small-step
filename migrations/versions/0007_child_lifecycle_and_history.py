"""Support child retirement while preserving historical records.

Revision ID: 0007_child_lifecycle_and_history
Revises: 0006_notification_rescheduling
Create Date: 2026-08-30
"""

from alembic import op
import sqlalchemy as sa


revision = "0007_child_lifecycle_and_history"
down_revision = "0006_notification_rescheduling"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("children", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("children", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_children_is_active", "children", ["is_active"], unique=False)
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TYPE auditeventaction ADD VALUE IF NOT EXISTS 'child_updated'")
        op.execute("ALTER TYPE auditeventaction ADD VALUE IF NOT EXISTS 'child_archived'")


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        raise RuntimeError("child lifecycle audit actions cannot be removed safely")
    op.drop_index("ix_children_is_active", table_name="children")
    op.drop_column("children", "archived_at")
    op.drop_column("children", "is_active")
