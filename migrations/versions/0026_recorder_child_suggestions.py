"""Add opt-in recording names and non-authoritative child advice."""

import sqlalchemy as sa
from alembic import op

revision = "0026_recorder_child_suggestions"
down_revision = "0025_recorder_voiceprint"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("children", sa.Column("recording_names", sa.JSON(), nullable=False, server_default=sa.text("'[]'")))
    op.add_column("records", sa.Column("candidate_child_id", sa.String(36), nullable=True))


def downgrade() -> None:
    op.drop_column("records", "candidate_child_id")
    op.drop_column("children", "recording_names")
