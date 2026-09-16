"""Merge recorder-session and multi-sample voiceprint migration heads.

Revision ID: 0023_recording_voiceprint_merge
Revises: 0022_recording_sessions, 0022_voiceprint_multi_sample
Create Date: 2026-09-16
"""

revision = "0023_recording_voiceprint_merge"
down_revision = ("0022_recording_sessions", "0022_voiceprint_multi_sample")
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Join the two independently developed schema branches."""


def downgrade() -> None:
    """The merge revision contains no schema operations."""
