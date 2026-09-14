"""Audit pending-record assignment changes.

Revision ID: 0020_record_reassignment_audit
Revises: 0019_cloud_audio_candidate_category
Create Date: 2026-09-14
"""

from alembic import op


revision = "0020_record_reassignment_audit"
down_revision = "0019_cloud_audio_candidate_category"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TYPE auditeventaction ADD VALUE IF NOT EXISTS 'record_reassigned'")


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        raise RuntimeError("record-reassignment audit events cannot be removed safely")
