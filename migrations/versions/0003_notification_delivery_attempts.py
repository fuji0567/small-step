"""Record privacy-safe LINE delivery attempt metadata.

Revision ID: 0003_notification_delivery_attempts
Revises: 0002_cloud_audio_upload_deduplication
Create Date: 2026-08-30
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_notification_delivery_attempts"
down_revision = "0002_cloud_audio_upload_deduplication"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # These additions are supported directly by SQLite and PostgreSQL. Avoid a
    # table rebuild so an interrupted local migration cannot collide with a
    # leftover Alembic temporary table.
    op.add_column("notifications", sa.Column("delivery_attempts", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("notifications", sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("notifications", sa.Column("last_failure_kind", sa.String(length=48), nullable=True))


def downgrade() -> None:
    op.drop_column("notifications", "last_failure_kind")
    op.drop_column("notifications", "last_attempt_at")
    op.drop_column("notifications", "delivery_attempts")
