"""Add school trial mode and permanently non-deliverable trial work."""

import sqlalchemy as sa
from alembic import op

revision = "0027_school_trial_mode"
down_revision = "0026_recorder_child_suggestions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("schools", sa.Column("trial_mode", sa.Boolean(), nullable=False, server_default=sa.false()))
    for table in ("records", "recording_sessions", "cloud_audio_jobs"):
        op.add_column(table, sa.Column("is_trial", sa.Boolean(), nullable=False, server_default=sa.false()))
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TYPE notificationstatus ADD VALUE IF NOT EXISTS 'trial'")
        op.execute("ALTER TYPE auditeventaction ADD VALUE IF NOT EXISTS 'school_trial_mode_changed'")


def downgrade() -> None:
    # Removing the permanent classification could release test records to LINE.
    raise RuntimeError("Trial mode cannot be safely downgraded; retain the delivery guards")
