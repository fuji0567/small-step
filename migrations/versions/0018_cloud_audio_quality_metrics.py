"""Store anonymous aggregate cloud-audio quality metrics.

Revision ID: 0018_cloud_audio_quality_metrics
Revises: 0017_worker_heartbeats
Create Date: 2026-09-14
"""

import sqlalchemy as sa
from alembic import op


revision = "0018_cloud_audio_quality_metrics"
down_revision = "0017_worker_heartbeats"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "cloud_audio_jobs",
        sa.Column("detected_speaker_count", sa.Integer(), nullable=True),
    )
    op.add_column(
        "cloud_audio_jobs",
        sa.Column("used_low_volume_retry", sa.Boolean(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("cloud_audio_jobs", "used_low_volume_retry")
    op.drop_column("cloud_audio_jobs", "detected_speaker_count")
