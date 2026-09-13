"""Monitor the VRT stack from a separate container and alert an operator."""

from __future__ import annotations

import argparse
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

from app.config import Settings
from app.line import LineMessagingError, push_text_message
from app.operations_monitor import (
    collect_operations_issues,
    complete_notification,
    format_notification,
    load_monitor_state,
    observe_issues,
    plan_notification,
    prepare_notification,
    save_monitor_state,
)


def run_monitor_once(*, settings: Settings, dry_run: bool = False) -> tuple[str, ...]:
    now = datetime.now(timezone.utc)
    state_path = Path(settings.operations_monitor_state_path)
    disk_paths = [
        Path(value.strip())
        for value in settings.operations_disk_paths.split(",")
        if value.strip()
    ]
    issues = collect_operations_issues(
        api_readiness_url=settings.operations_api_readiness_url,
        vllm_health_url=settings.operations_vllm_health_url,
        backup_dir=Path(settings.operations_backup_dir),
        backup_max_age=timedelta(hours=settings.operations_backup_max_age_hours),
        disk_paths=disk_paths,
        min_disk_free_bytes=int(settings.operations_min_disk_free_gb * 1024**3),
        timeout_seconds=settings.operations_check_timeout_seconds,
        now=now,
    )
    issue_codes = tuple(issue.code for issue in issues)
    state = observe_issues(load_monitor_state(state_path), issue_codes, now=now)
    plan = plan_notification(
        state,
        now=now,
        alert_after=timedelta(seconds=settings.operations_alert_after_seconds),
        repeat_after=timedelta(seconds=settings.operations_alert_repeat_seconds),
    )

    if dry_run:
        print("運用監視: " + ("正常" if not issue_codes else f"要確認={len(issue_codes)}件"))
        for code in issue_codes:
            print(f"- {code}")
        return issue_codes

    save_monitor_state(state_path, state)
    if plan is None:
        print("運用監視: " + ("正常" if not issue_codes else "異常の継続時間を確認中"))
        return issue_codes

    pending_state, retry_key = prepare_notification(state, plan, now=now)
    save_monitor_state(state_path, pending_state)
    try:
        push_text_message(
            channel_access_token=settings.line_channel_access_token or "",
            recipient_line_user_id=settings.operations_alert_line_user_id or "",
            text=format_notification(
                plan,
                issues=issues,
                now=now,
                timezone_name=settings.timezone,
            ),
            retry_key=retry_key,
            timeout_seconds=settings.line_api_timeout_seconds,
        )
    except (httpx.HTTPError, LineMessagingError) as error:
        print(f"運用通知の送信に失敗しました（{type(error).__name__}）。")
        return issue_codes

    save_monitor_state(state_path, complete_notification(pending_state, plan, now=now))
    print("運用監視: 復旧通知を送信しました" if plan.kind == "recovery" else "運用監視: 警告を送信しました")
    return issue_codes


def main() -> None:
    parser = argparse.ArgumentParser(description="Small Step VRTの稼働状態を監視します。")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--watch", action="store_true", help="継続して監視します")
    mode.add_argument("--dry-run", action="store_true", help="LINEへ送信せず1回だけ確認します")
    mode.add_argument(
        "--send-test-notification",
        action="store_true",
        help="運用責任者へ個人情報を含まないテスト通知を1回送ります",
    )
    parser.add_argument("--poll-seconds", type=float, help="監視間隔を一時的に上書きします")
    args = parser.parse_args()

    settings = Settings()
    if not args.dry_run:
        if not settings.line_channel_access_token or not settings.operations_alert_line_user_id:
            raise SystemExit(
                "LINE_CHANNEL_ACCESS_TOKEN と OPERATIONS_ALERT_LINE_USER_ID を設定してください。"
            )
        if not args.send_test_notification and not settings.operations_monitor_enabled:
            raise SystemExit("OPERATIONS_MONITOR_ENABLED=true を設定してから起動してください。")

    if args.send_test_notification:
        try:
            push_text_message(
                channel_access_token=settings.line_channel_access_token or "",
                recipient_line_user_id=settings.operations_alert_line_user_id or "",
                text="【Small Step 運用監視テスト】\n障害通知の送信先を確認しました。",
                retry_key=str(uuid.uuid4()),
                timeout_seconds=settings.line_api_timeout_seconds,
            )
        except (httpx.HTTPError, LineMessagingError) as error:
            raise SystemExit(
                f"運用監視テストの送信に失敗しました（{type(error).__name__}）。"
            ) from error
        print("運用監視テストを送信しました。")
        return

    poll_seconds = (
        args.poll_seconds
        if args.poll_seconds is not None
        else settings.operations_monitor_poll_seconds
    )
    if poll_seconds < 10:
        raise SystemExit("--poll-seconds は10秒以上にしてください。")

    if not args.watch:
        run_monitor_once(settings=settings, dry_run=args.dry_run)
        return

    while True:
        run_monitor_once(settings=settings)
        time.sleep(poll_seconds)


if __name__ == "__main__":
    main()
