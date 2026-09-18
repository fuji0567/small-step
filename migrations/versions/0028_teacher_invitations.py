"""Track invitation send times and durable resend cooldowns without tokens."""

import sqlalchemy as sa
from alembic import op

revision = "0028_teacher_invitations"
down_revision = "0027_school_trial_mode"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for name in ("invitation_attempted_at", "invitation_sent_at"):
        op.add_column(
            "teachers", sa.Column(name, sa.DateTime(timezone=True), nullable=True)
        )


def downgrade() -> None:
    op.drop_column("teachers", "invitation_sent_at")
    op.drop_column("teachers", "invitation_attempted_at")
