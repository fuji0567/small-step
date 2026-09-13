import hashlib
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import httpx

from app.operations_monitor import (
    MonitorState,
    NotificationPlan,
    OperationsIssue,
    collect_operations_issues,
    complete_notification,
    format_notification,
    load_monitor_state,
    observe_issues,
    plan_notification,
    prepare_notification,
    save_monitor_state,
)


NOW = datetime(2026, 9, 14, 3, 0, tzinfo=timezone.utc)


def write_backup(backup_dir: Path, *, content: bytes = b"backup") -> Path:
    backup_dir.mkdir()
    archive = backup_dir / "small-step-public-20260914T020000000000Z.dump"
    archive.write_bytes(content)
    archive.with_suffix(".dump.sha256").write_text(
        f"{hashlib.sha256(content).hexdigest()}  {archive.name}\n",
        encoding="ascii",
    )
    timestamp = (NOW - timedelta(hours=1)).timestamp()
    os.utime(archive, (timestamp, timestamp))
    return archive


def healthy_readiness() -> dict[str, object]:
    return {
        "status": "ready",
        "database_ready": True,
        "database_migration_current": True,
        "cloud_audio_enabled": True,
        "cloud_audio_job_storage_ready": True,
        "cloud_audio_llm_configured": True,
        "cloud_audio_worker_ready": True,
        "line_delivery_configured": True,
        "line_delivery_worker_ready": True,
    }


def collect(tmp_path: Path, requester, disk_usage=lambda _path: SimpleNamespace(free=20 * 1024**3)):
    backup_dir = tmp_path / "backups"
    write_backup(backup_dir)
    return collect_operations_issues(
        api_readiness_url="http://api/readiness",
        vllm_health_url="http://vllm/health",
        backup_dir=backup_dir,
        backup_max_age=timedelta(hours=26),
        disk_paths=[Path("/data")],
        min_disk_free_bytes=10 * 1024**3,
        timeout_seconds=3,
        now=NOW,
        requester=requester,
        disk_usage=disk_usage,
    )


def test_collect_operations_issues_accepts_healthy_services_and_backup(tmp_path):
    def requester(url, **_kwargs):
        if url.endswith("/readiness"):
            return httpx.Response(200, json=healthy_readiness())
        return httpx.Response(200)

    assert collect(tmp_path, requester) == ()


def test_collect_operations_issues_reports_safe_component_codes(tmp_path):
    def requester(url, **_kwargs):
        if url.endswith("/readiness"):
            payload = healthy_readiness()
            payload.update(
                status="not_ready",
                database_ready=False,
                cloud_audio_worker_ready=False,
                line_delivery_worker_ready=False,
            )
            return httpx.Response(503, json=payload)
        return httpx.Response(503)

    issues = collect(
        tmp_path,
        requester,
        disk_usage=lambda _path: SimpleNamespace(free=2 * 1024**3),
    )

    assert {issue.code for issue in issues} == {
        "database_unavailable",
        "disk_space_low",
        "gpu_worker_stopped",
        "line_worker_stopped",
        "vllm_unreachable",
    }
    assert all("http" not in issue.message for issue in issues)


def test_collect_operations_issues_detects_stale_or_modified_backup(tmp_path):
    def requester(url, **_kwargs):
        return (
            httpx.Response(200, json=healthy_readiness())
            if url.endswith("/readiness")
            else httpx.Response(200)
        )

    backup_dir = tmp_path / "backups"
    archive = write_backup(backup_dir)
    archive.write_bytes(b"modified")
    old_timestamp = (NOW - timedelta(hours=30)).timestamp()
    os.utime(archive, (old_timestamp, old_timestamp))

    issues = collect_operations_issues(
        api_readiness_url="http://api/readiness",
        vllm_health_url="http://vllm/health",
        backup_dir=backup_dir,
        backup_max_age=timedelta(hours=26),
        disk_paths=[],
        min_disk_free_bytes=10 * 1024**3,
        timeout_seconds=3,
        now=NOW,
        requester=requester,
    )

    assert {issue.code for issue in issues} == {"backup_invalid", "backup_stale"}


def test_notification_waits_repeats_and_recovers_without_duplicates():
    state = observe_issues(MonitorState(), ["api_unreachable"], now=NOW)
    assert plan_notification(
        state,
        now=NOW + timedelta(seconds=179),
        alert_after=timedelta(seconds=180),
        repeat_after=timedelta(hours=6),
    ) is None

    alert = plan_notification(
        state,
        now=NOW + timedelta(seconds=180),
        alert_after=timedelta(seconds=180),
        repeat_after=timedelta(hours=6),
    )
    assert alert == NotificationPlan("alert", ("api_unreachable",), "alert:api_unreachable")
    pending, retry_key = prepare_notification(
        state,
        alert,
        now=NOW + timedelta(seconds=180),
    )
    retried, retried_key = prepare_notification(
        pending,
        alert,
        now=NOW + timedelta(hours=1),
    )
    assert retried == pending
    assert retried_key == retry_key

    expired, expired_key = prepare_notification(
        pending,
        alert,
        now=NOW + timedelta(hours=24),
    )
    assert expired_key != retry_key
    assert expired.pending_created_at == NOW + timedelta(hours=24)

    alerted = complete_notification(pending, alert, now=NOW + timedelta(seconds=180))
    assert plan_notification(
        alerted,
        now=NOW + timedelta(hours=5),
        alert_after=timedelta(seconds=180),
        repeat_after=timedelta(hours=6),
    ) is None
    reminder = plan_notification(
        alerted,
        now=NOW + timedelta(hours=7),
        alert_after=timedelta(seconds=180),
        repeat_after=timedelta(hours=6),
    )
    assert reminder is not None
    assert reminder.kind == "reminder"

    recovered = observe_issues(alerted, [], now=NOW + timedelta(hours=7))
    recovery = plan_notification(
        recovered,
        now=NOW + timedelta(hours=7),
        alert_after=timedelta(seconds=180),
        repeat_after=timedelta(hours=6),
    )
    assert recovery == NotificationPlan("recovery", (), "recovery")


def test_monitor_state_round_trip_contains_only_operational_codes(tmp_path):
    path = tmp_path / "state" / "monitor.json"
    state = MonitorState(
        observed_issue_codes=("gpu_worker_stopped",),
        observed_since=NOW,
        notified_issue_codes=("gpu_worker_stopped",),
        last_notification_at=NOW,
        pending_signature="alert:gpu_worker_stopped",
        pending_retry_key="53d268f1-ae35-4ebd-8793-d87d84556361",
        pending_created_at=NOW,
    )

    save_monitor_state(path, state)

    assert load_monitor_state(path) == state
    assert path.stat().st_mode & 0o777 == 0o600
    saved = path.read_text(encoding="utf-8")
    assert "園児" not in saved
    assert "http" not in saved


def test_notification_text_omits_private_values():
    issue = OperationsIssue("api_unreachable", "先生用APIが応答していません。")
    plan = NotificationPlan("alert", (issue.code,), "alert:api_unreachable")

    message = format_notification(
        plan,
        issues=[issue],
        now=NOW,
        timezone_name="Asia/Tokyo",
    )

    assert "先生用APIが応答していません" in message
    assert "園児・音声・接続情報は含まれていません" in message
    assert "http" not in message
