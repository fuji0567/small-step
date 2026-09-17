"""Add explicit recorder identification consent and non-authoritative suggestions."""

import sqlalchemy as sa
from alembic import op

revision = "0025_recorder_voiceprint"
down_revision = "0024_recorder_worker"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("voice_enrollment_consents", sa.Column(
        "allows_recorder_identification", sa.Boolean(), nullable=False, server_default=sa.false(),
    ))
    op.add_column("records", sa.Column("voiceprint_candidate_teacher_id", sa.String(36), nullable=True))
    op.add_column("records", sa.Column(
        "voiceprint_matching_checked", sa.Boolean(), nullable=False, server_default=sa.false(),
    ))


def downgrade() -> None:
    op.drop_column("records", "voiceprint_matching_checked")
    op.drop_column("records", "voiceprint_candidate_teacher_id")
    op.drop_column("voice_enrollment_consents", "allows_recorder_identification")
