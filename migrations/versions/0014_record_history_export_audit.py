"""Audit record-history CSV exports.

Revision ID: 0014_record_history_export_audit
Revises: 0013_guardian_link_delivery_waiting
Create Date: 2026-08-31
"""

from alembic import op


revision = "0014_record_history_export_audit"
down_revision = "0013_guardian_link_delivery_waiting"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TYPE auditeventaction ADD VALUE IF NOT EXISTS 'record_history_exported'")


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        raise RuntimeError("record-history export audit events cannot be removed safely")
