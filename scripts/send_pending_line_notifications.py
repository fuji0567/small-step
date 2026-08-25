"""Deliver due guardian notifications through the LINE Messaging API.

Run this script from a scheduler on the API host. It operates directly on the
same database as the API, so it does not require a teacher access token.
"""

import argparse

import httpx
from sqlalchemy import select

from app.config import get_settings
from app.database import create_database_engine, create_session_factory, initialise_database
from app.line import LineMessagingError, build_notification_text, push_text_message
from app.models import Notification, NotificationStatus, Record, RecordStatus, utc_now


def send_due_notifications(*, retry_failed: bool = False, dry_run: bool = False) -> tuple[int, int]:
    settings = get_settings()
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
                if record is None or not notification.recipient_line_user_id:
                    notification.status = NotificationStatus.failed
                    session.commit()
                    failed_count += 1
                    continue

                if dry_run:
                    print(f"Would send notification {notification.id} to {notification.recipient_line_user_id}")
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
                    notification.status = NotificationStatus.failed
                    session.commit()
                    failed_count += 1
                    print(f"Failed notification {notification.id}: {error}")
                    continue

                notification.status = NotificationStatus.sent
                notification.provider_message_id = request_id
                notification.sent_at = utc_now()
                record.status = RecordStatus.dispatched
                session.commit()
                sent_count += 1
                print(f"Sent notification {notification.id}")
    finally:
        engine.dispose()

    return sent_count, failed_count


def main() -> None:
    parser = argparse.ArgumentParser(description="Send due Small Step notifications through LINE")
    parser.add_argument("--dry-run", action="store_true", help="List due notifications without sending them")
    parser.add_argument("--retry-failed", action="store_true", help="Also retry notifications marked as failed")
    args = parser.parse_args()
    sent, failed = send_due_notifications(retry_failed=args.retry_failed, dry_run=args.dry_run)
    print(f"Completed: sent={sent}, failed={failed}")


if __name__ == "__main__":
    main()

