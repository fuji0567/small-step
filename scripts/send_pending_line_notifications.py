"""Deliver due guardian notifications through the LINE Messaging API.

This worker operates directly on the same database as the API, so it does not
require a teacher access token. It only sends pending notices by default;
failed notices require an explicit manual retry.
"""

import argparse
import time

import httpx
from sqlalchemy import select

from app.config import Settings, get_settings
from app.database import create_database_engine, create_session_factory, initialise_database
from app.line import LineMessagingError, build_notification_text, push_text_message
from app.models import (
    Child,
    ClassNewsletter,
    ClassNewsletterRecipient,
    Classroom,
    GrowthDeliveryBatch,
    GrowthDeliveryEntry,
    Notification,
    NotificationStatus,
    Record,
    RecordCategory,
    RecordStatus,
    School,
    utc_now,
)
from app.worker_heartbeat import LINE_DELIVERY_WORKER_NAME, WorkerHeartbeatMonitor
from app.trial import lock_school


FAILURE_GUARDIAN_NOT_LINKED = "guardian_not_linked"
FAILURE_NETWORK = "network"
FAILURE_LINE_REJECTED = "line_rejected"
FAILURE_LINE_UNAVAILABLE = "line_unavailable"
FAILURE_UNKNOWN = "unknown"


def line_failure_kind(error: Exception) -> str:
    """Classify delivery failures without retaining provider response text."""

    if isinstance(error, httpx.TransportError):
        return FAILURE_NETWORK
    if isinstance(error, LineMessagingError):
        if error.status_code is not None and error.status_code >= 500:
            return FAILURE_LINE_UNAVAILABLE
        return FAILURE_LINE_REJECTED
    return FAILURE_UNKNOWN


def send_due_notifications(
    *,
    retry_failed: bool = False,
    dry_run: bool = False,
    settings: Settings | None = None,
) -> tuple[int, int]:
    """Send due notifications once, without exposing guardian IDs in logs."""

    settings = settings or get_settings()
    if not dry_run and not settings.line_channel_access_token:
        # A deployment without LINE credentials must not change queued notices.
        return 0, 0

    engine = create_database_engine(settings.database_url)
    initialise_database(engine)
    session_factory = create_session_factory(engine)
    sent_count = 0
    failed_count = 0

    try:
        with session_factory() as session:
            eligible_statuses = [NotificationStatus.pending]
            if retry_failed:
                eligible_statuses.append(NotificationStatus.failed)
            notifications = list(
                session.scalars(
                    select(Notification)
                    .where(Notification.status.in_(eligible_statuses))
                    .where(Notification.scheduled_for <= utc_now())
                    .order_by(Notification.scheduled_for)
                )
            )

            for notification in notifications:
                record = session.get(Record, notification.record_id)
                if record is not None:
                    school = lock_school(session, record.school_id)
                    session.refresh(notification)
                    session.refresh(record)
                    if notification.status not in eligible_statuses:
                        session.commit()
                        continue
                    if record.is_trial or school.trial_mode:
                        record.is_trial = True
                        notification.status = NotificationStatus.trial
                        notification.recipient_line_user_id = None
                        session.commit()
                        continue
                    child = session.get(Child, record.child_id) if record.child_id else None
                    classroom = session.get(Classroom, child.classroom_id) if child and child.classroom_id else None
                    if record.category == RecordCategory.growth and classroom is not None:
                        entry = session.get(GrowthDeliveryEntry, notification.growth_delivery_entry_id) if notification.growth_delivery_entry_id else None
                        batch = session.get(GrowthDeliveryBatch, entry.batch_id) if entry else None
                        if entry is not None:
                            if (batch is None or not classroom.is_active or not classroom.delivery_enabled
                                    or not entry.selected or batch.status != "approved" or batch.is_trial
                                    or batch.school_id != record.school_id
                                    or batch.classroom_id != classroom.id
                                    or entry.school_id != record.school_id
                                    or entry.classroom_id != classroom.id
                                    or record.status != RecordStatus.approved
                                    or not child.is_active or child.school_id != record.school_id
                                    or child.classroom_id != classroom.id
                                    or child.guardian_line_user_id != notification.recipient_line_user_id
                                    or (child.guardian_line_linked_at is not None
                                        and batch.approved_at is not None
                                        and child.guardian_line_linked_at > batch.approved_at)):
                                notification.status = NotificationStatus.cancelled
                                notification.recipient_line_user_id = None
                                session.commit()
                                continue
                        elif (classroom.is_active and classroom.delivery_enabled
                              and classroom.delivery_enabled_since is not None
                              and notification.created_at >= classroom.delivery_enabled_since):
                            # Do not let a post-activation approval bypass today's teacher selection.
                            notification.status = NotificationStatus.cancelled
                            notification.recipient_line_user_id = None
                            session.commit()
                            continue
                    elif record.category == RecordCategory.growth and notification.growth_delivery_entry_id:
                        # A selected class-delivery notice must not fall back to legacy delivery after disablement.
                        notification.status = NotificationStatus.cancelled
                        notification.recipient_line_user_id = None
                        session.commit()
                        continue
                if record is None or not notification.recipient_line_user_id:
                    notification.status = NotificationStatus.failed
                    notification.last_failure_kind = FAILURE_GUARDIAN_NOT_LINKED
                    session.commit()
                    failed_count += 1
                    continue

                if dry_run:
                    sent_count += 1
                    continue

                try:
                    request_id = push_text_message(
                        channel_access_token=settings.line_channel_access_token or "",
                        recipient_line_user_id=notification.recipient_line_user_id,
                        text=build_notification_text(
                            summary=record.summary,
                            conversation_prompt=record.conversation_prompt,
                        ),
                        retry_key=notification.id,
                        timeout_seconds=settings.line_api_timeout_seconds,
                    )
                except (httpx.HTTPError, LineMessagingError) as error:
                    notification.delivery_attempts += 1
                    notification.last_attempt_at = utc_now()
                    notification.status = NotificationStatus.failed
                    notification.last_failure_kind = line_failure_kind(error)
                    session.commit()
                    failed_count += 1
                    print(f"LINE送信に失敗しました（{type(error).__name__}）。")
                    continue

                notification.delivery_attempts += 1
                notification.last_attempt_at = utc_now()
                notification.status = NotificationStatus.sent
                notification.provider_message_id = request_id
                notification.last_failure_kind = None
                notification.sent_at = utc_now()
                record.status = RecordStatus.dispatched
                session.commit()
                sent_count += 1

            class_sent, class_failed = _send_due_class_newsletters(
                session=session,
                settings=settings,
                retry_failed=retry_failed,
                dry_run=dry_run,
            )
            sent_count += class_sent
            failed_count += class_failed
    finally:
        engine.dispose()

    return sent_count, failed_count


def _send_due_class_newsletters(*, session, settings, retry_failed: bool, dry_run: bool) -> tuple[int, int]:
    """Send each class newsletter to its snapshotted, deduplicated recipients."""
    statuses = ["pending"] + (["failed"] if retry_failed else [])
    rows = session.execute(
        select(ClassNewsletterRecipient, ClassNewsletter, Classroom, School)
        .join(ClassNewsletter, ClassNewsletter.id == ClassNewsletterRecipient.newsletter_id)
        .join(Classroom, Classroom.id == ClassNewsletter.classroom_id)
        .join(School, School.id == ClassNewsletter.school_id)
        .where(ClassNewsletterRecipient.status.in_(statuses))
        .where(ClassNewsletter.status == "approved")
        .where(ClassNewsletter.scheduled_for <= utc_now())
        .order_by(ClassNewsletter.scheduled_for, ClassNewsletterRecipient.id)
    ).all()
    sent = failed = 0
    for recipient, newsletter, classroom, school in rows:
        school = lock_school(session, newsletter.school_id)
        session.refresh(newsletter)
        session.refresh(classroom)
        session.refresh(school)
        session.refresh(recipient)
        if recipient.status not in statuses:
            continue
        if (newsletter.is_trial or school.trial_mode or not classroom.is_active
                or not classroom.delivery_enabled or newsletter.status != "approved"):
            recipient.status = "trial" if newsletter.is_trial or school.trial_mode else "cancelled"
            session.commit()
            continue
        still_linked = session.scalar(select(Child.id).where(
            Child.school_id == school.id, Child.classroom_id == classroom.id,
            Child.is_active.is_(True), Child.guardian_line_user_id == recipient.recipient_line_user_id,
            Child.id.in_(recipient.child_ids or []),
            Child.guardian_line_linked_at.is_(None)
            | (Child.guardian_line_linked_at <= newsletter.approved_at),
        ).limit(1))
        if still_linked is None:
            recipient.status = "cancelled"
            recipient.last_failure_kind = "recipient_no_longer_linked"
            session.commit()
            continue
        if dry_run:
            sent += 1
            continue
        try:
            request_id = push_text_message(
                channel_access_token=settings.line_channel_access_token or "",
                recipient_line_user_id=recipient.recipient_line_user_id,
                text=newsletter.body,
                retry_key=recipient.id,
                timeout_seconds=settings.line_api_timeout_seconds,
            )
        except (httpx.HTTPError, LineMessagingError) as error:
            recipient.delivery_attempts += 1
            recipient.status = "failed"
            recipient.last_failure_kind = line_failure_kind(error)
            session.commit()
            failed += 1
            print(f"クラスお便りのLINE送信に失敗しました（{type(error).__name__}）。")
            continue
        recipient.delivery_attempts += 1
        recipient.status = "sent"
        recipient.provider_message_id = request_id
        recipient.sent_at = utc_now()
        recipient.last_failure_kind = None
        session.commit()
        sent += 1
    return sent, failed


def main() -> None:
    parser = argparse.ArgumentParser(description="Send due Small Step notifications through LINE")
    parser.add_argument("--dry-run", action="store_true", help="List due notifications without sending them")
    parser.add_argument("--retry-failed", action="store_true", help="Also retry notifications marked as failed")
    parser.add_argument("--watch", action="store_true", help="継続して配信待ち通知を確認します")
    parser.add_argument(
        "--poll-seconds",
        type=float,
        help="待機秒数。既定値は LINE_WORKER_POLL_SECONDS です。",
    )
    args = parser.parse_args()
    if args.watch and args.dry_run:
        raise SystemExit("--watch と --dry-run は同時に指定できません。")

    settings = get_settings()
    poll_seconds = args.poll_seconds if args.poll_seconds is not None else settings.line_worker_poll_seconds
    if poll_seconds <= 0:
        raise SystemExit("--poll-seconds は0より大きい値にしてください。")
    if not args.dry_run and not settings.line_channel_access_token:
        raise SystemExit("LINE_CHANNEL_ACCESS_TOKEN を設定してから起動してください。")

    if not args.watch:
        sent, failed = send_due_notifications(
            retry_failed=args.retry_failed,
            dry_run=args.dry_run,
            settings=settings,
        )
        mode_label = "確認" if args.dry_run else "送信"
        print(f"LINE通知 {mode_label}: 対象={sent}件, 失敗={failed}件")
        return

    engine = create_database_engine(settings.database_url)
    initialise_database(engine)
    session_factory = create_session_factory(engine)
    try:
        with WorkerHeartbeatMonitor(
            session_factory=session_factory,
            worker_name=LINE_DELIVERY_WORKER_NAME,
            interval_seconds=settings.worker_heartbeat_interval_seconds,
        ):
            while True:
                sent, failed = send_due_notifications(
                    retry_failed=args.retry_failed,
                    dry_run=False,
                    settings=settings,
                )
                print(f"LINE通知 送信: 対象={sent}件, 失敗={failed}件")
                time.sleep(poll_seconds)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
