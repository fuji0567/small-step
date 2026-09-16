"""Add recorder worker leases and content-free progress counters."""

import sqlalchemy as sa
from alembic import op


revision = "0024_recorder_worker"
down_revision = "0023_recording_voiceprint_merge"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("recording_sessions", sa.Column("claim_token", sa.String(36), nullable=True))
    op.add_column(
        "recording_sessions",
        sa.Column("processed_segment_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "recording_sessions",
        sa.Column("failed_segment_count", sa.Integer(), server_default="0", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("recording_sessions", "failed_segment_count")
    op.drop_column("recording_sessions", "processed_segment_count")
    op.drop_column("recording_sessions", "claim_token")
