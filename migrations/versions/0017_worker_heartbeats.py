"""Track background worker liveness without storing job contents.

Revision ID: 0017_worker_heartbeats
Revises: 0016_protect_supabase_tables
Create Date: 2026-09-13
"""

import sqlalchemy as sa
from alembic import op


revision = "0017_worker_heartbeats"
down_revision = "0016_protect_supabase_tables"
branch_labels = None
depends_on = None


def supabase_data_api_roles() -> tuple[str, ...]:
    roles = op.get_bind().execute(
        sa.text("SELECT rolname FROM pg_roles WHERE rolname IN ('anon', 'authenticated', 'service_role')")
    )
    return tuple(roles.scalars())


def upgrade() -> None:
    op.create_table(
        "worker_heartbeats",
        sa.Column("worker_name", sa.String(length=64), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("worker_name"),
    )

    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute('ALTER TABLE public."worker_heartbeats" ENABLE ROW LEVEL SECURITY')
    for role in supabase_data_api_roles():
        op.execute(f'REVOKE ALL PRIVILEGES ON TABLE public."worker_heartbeats" FROM "{role}"')


def downgrade() -> None:
    op.drop_table("worker_heartbeats")
