"""Fence cloud audio workers with short-lived claim tokens.

Revision ID: 0004_cloud_audio_worker_leases
Revises: 0003_notification_delivery_attempts
Create Date: 2026-08-30
"""

from alembic import op
import sqlalchemy as sa


revision = "0004_cloud_audio_worker_leases"
down_revision = "0003_notification_delivery_attempts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("cloud_audio_jobs", sa.Column("claim_token", sa.String(length=36), nullable=True))


def downgrade() -> None:
    op.drop_column("cloud_audio_jobs", "claim_token")
