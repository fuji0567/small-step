"""Store the aggregate candidate category for audio evaluation.

Revision ID: 0019_cloud_audio_candidate_category
Revises: 0018_cloud_audio_quality_metrics
Create Date: 2026-09-14
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "0019_cloud_audio_candidate_category"
down_revision = "0018_cloud_audio_quality_metrics"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        record_category = postgresql.ENUM(
            "growth", "injury", name="recordcategory", create_type=False
        )
    else:
        record_category = sa.Enum("growth", "injury", name="recordcategory")
    op.add_column(
        "cloud_audio_jobs",
        sa.Column("candidate_category", record_category, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("cloud_audio_jobs", "candidate_category")
