"""Add a safe waiting state for notifications without a guardian LINE link.

Revision ID: 0013_guardian_link_delivery_waiting
Revises: 0012_manual_record_creation
Create Date: 2026-08-31
"""

from alembic import op


revision = "0013_guardian_link_delivery_waiting"
down_revision = "0012_manual_record_creation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TYPE notificationstatus ADD VALUE IF NOT EXISTS 'waiting_guardian_link'")


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        raise RuntimeError("guardian-link waiting notifications cannot be removed safely")
