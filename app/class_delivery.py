"""Suspend class delivery without deleting rosters or accepted delivery history."""

from sqlalchemy import select, union, update
from sqlalchemy.orm import Session

from app.models import (
    Classroom, ClassNewsletter, ClassNewsletterRecipient, GrowthDeliveryBatch,
    GrowthDeliveryEntry, Notification, NotificationStatus, utc_now,
)
from app.trial import lock_school


UNSENT_PERSONAL_STATUSES = (
    NotificationStatus.pending, NotificationStatus.waiting_guardian_link,
    NotificationStatus.failed,
)
UNSENT_CLASS_STATUSES = ("pending", "failed")


def sync_class_delivery_mode(db: Session, *, enabled: bool) -> None:
    """Apply mode transitions under the same school locks used by delivery.

    The caller commits. A null activation time on an opted-in class records a
    pause; resuming sets a new boundary so legacy notices made during the pause
    can still be sent. Cancelled class work is never revived.
    """

    opted_in_schools = select(Classroom.school_id).where(
        Classroom.delivery_enabled.is_(True),
        Classroom.delivery_enabled_since.is_(None) if enabled
        else Classroom.delivery_enabled_since.is_not(None),
    )
    if enabled:
        school_ids = db.scalars(opted_in_schools.distinct()).all()
    else:
        school_ids = db.scalars(union(
            opted_in_schools,
            select(ClassNewsletter.school_id)
            .join(ClassNewsletterRecipient, ClassNewsletterRecipient.newsletter_id == ClassNewsletter.id)
            .where(ClassNewsletterRecipient.status.in_(UNSENT_CLASS_STATUSES)),
            select(GrowthDeliveryEntry.school_id)
            .join(Notification, Notification.growth_delivery_entry_id == GrowthDeliveryEntry.id)
            .where(Notification.status.in_(UNSENT_PERSONAL_STATUSES)),
        )).all()
    for school_id in sorted(school_ids):
        lock_school(db, school_id)
        now = utc_now()
        if enabled:
            db.execute(update(Classroom).where(
                Classroom.school_id == school_id,
                Classroom.delivery_enabled.is_(True),
                Classroom.delivery_enabled_since.is_(None),
            ).values(delivery_enabled_since=now))
            continue

        db.execute(update(Classroom).where(
            Classroom.school_id == school_id, Classroom.delivery_enabled.is_(True),
        ).values(delivery_enabled_since=None))
        pending_newsletters = select(ClassNewsletterRecipient.newsletter_id).where(
            ClassNewsletterRecipient.status.in_(UNSENT_CLASS_STATUSES),
        )
        db.execute(update(ClassNewsletter).where(
            ClassNewsletter.school_id == school_id,
            ClassNewsletter.status == "approved",
            ClassNewsletter.id.in_(pending_newsletters),
        ).values(status="cancelled", cancelled_at=now))
        db.execute(update(ClassNewsletterRecipient).where(
            ClassNewsletterRecipient.newsletter_id.in_(
                select(ClassNewsletter.id).where(ClassNewsletter.school_id == school_id)
            ),
            ClassNewsletterRecipient.status.in_(UNSENT_CLASS_STATUSES),
        ).values(status="cancelled"))
        pending_batches = select(GrowthDeliveryEntry.batch_id).join(
            Notification, Notification.growth_delivery_entry_id == GrowthDeliveryEntry.id,
        ).where(Notification.status.in_(UNSENT_PERSONAL_STATUSES))
        db.execute(update(GrowthDeliveryBatch).where(
            GrowthDeliveryBatch.school_id == school_id,
            GrowthDeliveryBatch.status == "approved",
            GrowthDeliveryBatch.id.in_(pending_batches),
        ).values(status="cancelled", cancelled_at=now))
        db.execute(update(Notification).where(
            Notification.growth_delivery_entry_id.in_(
                select(GrowthDeliveryEntry.id).where(GrowthDeliveryEntry.school_id == school_id)
            ),
            Notification.status.in_(UNSENT_PERSONAL_STATUSES),
        ).values(status=NotificationStatus.cancelled, recipient_line_user_id=None))
