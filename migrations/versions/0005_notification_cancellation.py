"""Allow an administrator to cancel queued LINE notifications.

Revision ID: 0005_notification_cancellation
Revises: 0004_cloud_audio_worker_leases
Create Date: 2026-08-30
"""

from alembic import op


revision = "0005_notification_cancellation"
down_revision = "0004_cloud_audio_worker_leases"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add the two enum values without rewriting notification history."""

    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TYPE notificationstatus ADD VALUE IF NOT EXISTS 'cancelled'")
        op.execute("ALTER TYPE auditeventaction ADD VALUE IF NOT EXISTS 'notification_cancelled'")


def downgrade() -> None:
    """PostgreSQL cannot safely remove enum values from live history."""

    if op.get_bind().dialect.name == "postgresql":
        raise RuntimeError("notification cancellation enum values cannot be removed safely")
