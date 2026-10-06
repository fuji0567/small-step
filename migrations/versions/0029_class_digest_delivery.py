"""Add class rosters, class newsletters, and fair individual delivery batches."""

import sqlalchemy as sa
from alembic import op

revision = "0029_class_digest_delivery"
down_revision = "0028_teacher_invitations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "classrooms",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("school_id", sa.String(36), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("delivery_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("delivery_enabled_since", sa.DateTime(timezone=True), nullable=True),
        sa.Column("daily_growth_limit", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("school_id", "name", name="uq_classroom_school_name"),
    )
    op.create_index("ix_classrooms_school_id", "classrooms", ["school_id"])
    op.create_index("ix_classrooms_is_active", "classrooms", ["is_active"])
    with op.batch_alter_table("children") as batch_op:
        batch_op.add_column(
            sa.Column(
                "classroom_id", sa.String(36),
                sa.ForeignKey("classrooms.id", name="fk_children_classroom_id_classrooms"),
                nullable=True,
            )
        )
        batch_op.add_column(sa.Column("guardian_line_linked_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_children_classroom_id", "children", ["classroom_id"])

    op.create_table(
        "class_newsletters",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("school_id", sa.String(36), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("classroom_id", sa.String(36), sa.ForeignKey("classrooms.id"), nullable=False),
        sa.Column("delivery_date", sa.String(10), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_trial", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_by_teacher_id", sa.String(36), sa.ForeignKey("teachers.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("classroom_id", "delivery_date", name="uq_class_newsletter_day"),
    )
    op.create_index("ix_class_newsletters_school_id", "class_newsletters", ["school_id"])
    op.create_index("ix_class_newsletters_classroom_id", "class_newsletters", ["classroom_id"])
    op.create_index("ix_class_newsletters_delivery_date", "class_newsletters", ["delivery_date"])
    op.create_index("ix_class_newsletters_status", "class_newsletters", ["status"])
    op.create_index("ix_class_newsletters_scheduled_for", "class_newsletters", ["scheduled_for"])
    op.create_index("ix_class_newsletters_created_by_teacher_id", "class_newsletters", ["created_by_teacher_id"])

    op.create_table(
        "class_newsletter_recipients",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("newsletter_id", sa.String(36), sa.ForeignKey("class_newsletters.id"), nullable=False),
        sa.Column("recipient_line_user_id", sa.String(255), nullable=False),
        sa.Column("child_ids", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="pending"),
        sa.Column("delivery_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_failure_kind", sa.String(48), nullable=True),
        sa.Column("provider_message_id", sa.String(255), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("newsletter_id", "recipient_line_user_id", name="uq_class_newsletter_recipient"),
    )
    op.create_index("ix_class_newsletter_recipients_newsletter_id", "class_newsletter_recipients", ["newsletter_id"])
    op.create_index("ix_class_newsletter_recipients_status", "class_newsletter_recipients", ["status"])

    op.create_table(
        "growth_delivery_batches",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("school_id", sa.String(36), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("classroom_id", sa.String(36), sa.ForeignKey("classrooms.id"), nullable=False),
        sa.Column("delivery_date", sa.String(10), nullable=False),
        sa.Column("daily_limit", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_trial", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_by_teacher_id", sa.String(36), sa.ForeignKey("teachers.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("classroom_id", "delivery_date", name="uq_growth_delivery_batch_day"),
    )
    op.create_index("ix_growth_delivery_batches_school_id", "growth_delivery_batches", ["school_id"])
    op.create_index("ix_growth_delivery_batches_classroom_id", "growth_delivery_batches", ["classroom_id"])
    op.create_index("ix_growth_delivery_batches_delivery_date", "growth_delivery_batches", ["delivery_date"])
    op.create_index("ix_growth_delivery_batches_status", "growth_delivery_batches", ["status"])
    op.create_index("ix_growth_delivery_batches_scheduled_for", "growth_delivery_batches", ["scheduled_for"])
    op.create_index("ix_growth_delivery_batches_created_by_teacher_id", "growth_delivery_batches", ["created_by_teacher_id"])

    op.create_table(
        "growth_delivery_entries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("batch_id", sa.String(36), sa.ForeignKey("growth_delivery_batches.id"), nullable=False),
        sa.Column("school_id", sa.String(36), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("classroom_id", sa.String(36), sa.ForeignKey("classrooms.id"), nullable=False),
        sa.Column("record_id", sa.String(36), sa.ForeignKey("records.id"), nullable=False),
        sa.Column("child_id", sa.String(36), sa.ForeignKey("children.id"), nullable=False),
        sa.Column("selected", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("batch_id", "record_id", name="uq_growth_delivery_batch_record"),
        sa.UniqueConstraint("batch_id", "child_id", name="uq_growth_delivery_batch_child"),
    )
    op.create_index("ix_growth_delivery_entries_batch_id", "growth_delivery_entries", ["batch_id"])
    op.create_index("ix_growth_delivery_entries_school_id", "growth_delivery_entries", ["school_id"])
    op.create_index("ix_growth_delivery_entries_classroom_id", "growth_delivery_entries", ["classroom_id"])
    op.create_index("ix_growth_delivery_entries_record_id", "growth_delivery_entries", ["record_id"])
    op.create_index("ix_growth_delivery_entries_child_id", "growth_delivery_entries", ["child_id"])
    op.create_index("ix_growth_delivery_entries_selected", "growth_delivery_entries", ["selected"])
    with op.batch_alter_table("notifications") as batch_op:
        batch_op.add_column(
            sa.Column(
                "growth_delivery_entry_id", sa.String(36),
                sa.ForeignKey("growth_delivery_entries.id", name="fk_notifications_growth_delivery_entry_id"),
                nullable=True,
            )
        )
        batch_op.create_unique_constraint(
            "uq_notifications_growth_delivery_entry", ["growth_delivery_entry_id"]
        )


def downgrade() -> None:
    # Downgrading could turn intentionally unselected approved records into legacy notifications.
    raise RuntimeError("Class delivery history cannot be safely downgraded")
