"""Deduplicate retried cloud audio uploads from one edge device.

Revision ID: 0002_cloud_audio_upload_deduplication
Revises: 0001_initial_schema
Create Date: 2026-08-30
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_cloud_audio_upload_deduplication"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("cloud_audio_jobs") as batch:
        batch.add_column(sa.Column("edge_upload_id", sa.String(length=36), nullable=True))
        batch.create_unique_constraint(
            "uq_cloud_audio_job_device_upload",
            ["device_id", "edge_upload_id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("cloud_audio_jobs") as batch:
        batch.drop_constraint("uq_cloud_audio_job_device_upload", type_="unique")
        batch.drop_column("edge_upload_id")
