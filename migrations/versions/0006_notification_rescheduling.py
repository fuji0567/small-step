"""Record scheduled-notification time changes in operational history.

Revision ID: 0006_notification_rescheduling
Revises: 0005_notification_cancellation
Create Date: 2026-08-30
"""

from alembic import op


revision = "0006_notification_rescheduling"
down_revision = "0005_notification_cancellation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TYPE auditeventaction ADD VALUE IF NOT EXISTS 'notification_rescheduled'")


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        raise RuntimeError("notification rescheduling enum value cannot be removed safely")
