"""Record safe child restoration actions.

Revision ID: 0008_child_restoration
Revises: 0007_child_lifecycle_and_history
Create Date: 2026-08-30
"""

from alembic import op


revision = "0008_child_restoration"
down_revision = "0007_child_lifecycle_and_history"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TYPE auditeventaction ADD VALUE IF NOT EXISTS 'child_restored'")


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        raise RuntimeError("child restoration audit actions cannot be removed safely")
