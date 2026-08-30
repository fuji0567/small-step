"""Audit operational-history CSV exports.

Revision ID: 0015_audit_history_export_audit
Revises: 0014_record_history_export_audit
Create Date: 2026-08-31
"""

from alembic import op


revision = "0015_audit_history_export_audit"
down_revision = "0014_record_history_export_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TYPE auditeventaction ADD VALUE IF NOT EXISTS 'audit_history_exported'")


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        raise RuntimeError("Audit-history export events cannot be removed safely")
