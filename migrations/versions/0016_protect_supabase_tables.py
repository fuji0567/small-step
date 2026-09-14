"""Protect application tables from direct Supabase Data API access.

Revision ID: 0016_protect_supabase_tables
Revises: 0015_audit_history_export_audit
Create Date: 2026-09-12
"""

import sqlalchemy as sa
from alembic import op


revision = "0016_protect_supabase_tables"
down_revision = "0015_audit_history_export_audit"
branch_labels = None
depends_on = None


APPLICATION_TABLES = (
    "schools",
    "teachers",
    "edge_devices",
    "voice_enrollment_consents",
    "cloud_audio_jobs",
    "children",
    "line_link_invitations",
    "guardian_archive_links",
    "audit_events",
    "records",
    "notifications",
    "notion_syncs",
)


def supabase_data_api_roles() -> tuple[str, ...]:
    roles = op.get_bind().execute(
        sa.text("SELECT rolname FROM pg_roles WHERE rolname IN ('anon', 'authenticated')")
    )
    return tuple(roles.scalars())


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return

    roles = supabase_data_api_roles()
    if not roles:
        return

    for table_name in APPLICATION_TABLES:
        op.execute(f'ALTER TABLE public."{table_name}" ENABLE ROW LEVEL SECURITY')
        for role in roles:
            op.execute(f'REVOKE ALL PRIVILEGES ON TABLE public."{table_name}" FROM "{role}"')


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql" and supabase_data_api_roles():
        raise RuntimeError("Supabase table protection cannot be removed safely")
