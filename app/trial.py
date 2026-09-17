"""Permanent trial classification and serialized guardian delivery gates."""

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import (
    CloudAudioJob, CloudAudioJobStatus, Notification, NotificationStatus,
    Record, RecordStatus, RecordingSession, RecordingSessionStatus, School,
)


def lock_school(db: Session, school_id: str) -> School:
    # Delivery holds this lock through the provider call. Mode changes wait for
    # in-flight delivery, then prevent subsequent sends before returning.
    school = db.scalar(select(School).where(School.id == school_id)
                       .with_for_update().execution_options(populate_existing=True))
    if school is None:
        raise ValueError("School is unavailable")
    return school


def protect_trial_work(db: Session, school_id: str) -> None:
    """Never release existing trial work when production delivery is enabled."""
    record_ids = select(Record.id).where(Record.school_id == school_id)
    queued_record_ids = select(Notification.record_id).where(
        Notification.record_id.in_(record_ids),
        Notification.status.in_([
            NotificationStatus.pending, NotificationStatus.waiting_guardian_link,
            NotificationStatus.failed,
        ]),
    )
    db.execute(update(Record).where(
        Record.school_id == school_id,
        (Record.status == RecordStatus.pending_review) | Record.id.in_(queued_record_ids),
    ).values(is_trial=True))
    db.execute(update(Notification).where(
        Notification.record_id.in_(record_ids),
        Notification.status.in_([
            NotificationStatus.pending, NotificationStatus.waiting_guardian_link,
            NotificationStatus.failed,
        ]),
    ).values(status=NotificationStatus.trial, recipient_line_user_id=None))
    db.execute(update(RecordingSession).where(
        RecordingSession.school_id == school_id,
        RecordingSession.status.in_([
            RecordingSessionStatus.draft, RecordingSessionStatus.queued,
            RecordingSessionStatus.processing,
        ]),
    ).values(is_trial=True))
    db.execute(update(CloudAudioJob).where(
        CloudAudioJob.school_id == school_id,
        CloudAudioJob.status.in_([CloudAudioJobStatus.queued, CloudAudioJobStatus.processing]),
    ).values(is_trial=True))
