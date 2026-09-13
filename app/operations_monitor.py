"""Privacy-safe health checks and notification state for VRT operations."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

import httpx

from app.database_backup import (
    DatabaseBackupError,
    backup_checksum_is_valid,
    latest_database_backup,
)


ISSUE_MESSAGES = {
    "api_unreachable": "先生用APIが応答していません。",
    "api_not_ready": "先生用APIの稼働準備が完了していません。",
    "database_unavailable": "業務データベースへ接続できません。",
    "database_migration_outdated": "データベース更新が未適用です。",
    "cloud_audio_storage_unavailable": "音声処理用の一時保存領域を利用できません。",
    "llm_not_configured": "文章生成AIの接続設定を確認できません。",
    "gpu_worker_stopped": "GPU音声処理が停止しています。",
    "line_not_configured": "LINE配信設定を確認できません。",
    "line_worker_stopped": "LINE送信処理が停止しています。",
    "vllm_unreachable": "文章生成AIが応答していません。",
    "backup_missing": "業務データのバックアップが見つかりません。",
    "backup_stale": "業務データのバックアップが所定時間更新されていません。",
    "backup_invalid": "最新バックアップのチェックサムを確認できません。",
    "disk_space_low": "サーバーの空き容量がしきい値を下回っています。",
    "disk_space_unavailable": "サーバーの保存領域を確認できません。",
}


@dataclass(frozen=True, order=True)
class OperationsIssue:
    code: str
    message: str


@dataclass(frozen=True)
class MonitorState:
    observed_issue_codes: tuple[str, ...] = ()
    observed_since: datetime | None = None
    notified_issue_codes: tuple[str, ...] = ()
    last_notification_at: datetime | None = None
    pending_signature: str | None = None
    pending_retry_key: str | None = None
    pending_created_at: datetime | None = None


@dataclass(frozen=True)
class NotificationPlan:
    kind: Literal["alert", "reminder", "recovery"]
    issue_codes: tuple[str, ...]
    signature: str


def _issue(code: str) -> OperationsIssue:
    return OperationsIssue(code=code, message=ISSUE_MESSAGES[code])


def _normalise_now(value: datetime | None) -> datetime:
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None:
        return current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc)


def _check_api_readiness(
    *,
    url: str,
    timeout_seconds: float,
    requester: Callable[..., httpx.Response],
) -> list[OperationsIssue]:
    try:
        response = requester(url, timeout=timeout_seconds)
        payload = response.json()
        if response.status_code not in {200, 503} or not isinstance(payload, dict):
            raise ValueError("unexpected readiness response")
    except (httpx.HTTPError, TypeError, ValueError):
        return [_issue("api_unreachable")]

    issues: list[OperationsIssue] = []
    if payload.get("database_ready") is not True:
        issues.append(_issue("database_unavailable"))
    if payload.get("database_migration_current") is not True:
        issues.append(_issue("database_migration_outdated"))

    if payload.get("cloud_audio_enabled") is True:
        if payload.get("cloud_audio_job_storage_ready") is not True:
            issues.append(_issue("cloud_audio_storage_unavailable"))
        if payload.get("cloud_audio_llm_configured") is not True:
            issues.append(_issue("llm_not_configured"))
        if payload.get("cloud_audio_worker_ready") is not True:
            issues.append(_issue("gpu_worker_stopped"))

    if payload.get("line_delivery_configured") is not True:
        issues.append(_issue("line_not_configured"))
    elif payload.get("line_delivery_worker_ready") is not True:
        issues.append(_issue("line_worker_stopped"))

    if payload.get("status") != "ready" and not issues:
        issues.append(_issue("api_not_ready"))
    return issues


def _check_vllm(
    *,
    url: str,
    timeout_seconds: float,
    requester: Callable[..., httpx.Response],
) -> list[OperationsIssue]:
    try:
        response = requester(url, timeout=timeout_seconds)
        if not response.is_success:
            raise ValueError("unexpected vLLM response")
    except (httpx.HTTPError, ValueError):
        return [_issue("vllm_unreachable")]
    return []


def _check_backup(
    *,
    backup_dir: Path,
    max_age: timedelta,
    now: datetime,
) -> list[OperationsIssue]:
    try:
        archive_path = latest_database_backup(backup_dir)
    except (DatabaseBackupError, OSError):
        return [_issue("backup_missing")]

    issues: list[OperationsIssue] = []
    try:
        modified_at = datetime.fromtimestamp(archive_path.stat().st_mtime, tz=timezone.utc)
        if now - modified_at > max_age:
            issues.append(_issue("backup_stale"))
    except OSError:
        issues.append(_issue("backup_invalid"))
        return issues
    if not backup_checksum_is_valid(archive_path):
        issues.append(_issue("backup_invalid"))
    return issues


def _check_disk_space(
    *,
    disk_paths: Sequence[Path],
    min_free_bytes: int,
    disk_usage: Callable[[Path], object],
) -> list[OperationsIssue]:
    low = False
    unavailable = False
    for path in disk_paths:
        try:
            usage = disk_usage(path)
            if int(getattr(usage, "free")) < min_free_bytes:
                low = True
        except (AttributeError, OSError, TypeError, ValueError):
            unavailable = True
    issues: list[OperationsIssue] = []
    if low:
        issues.append(_issue("disk_space_low"))
    if unavailable:
        issues.append(_issue("disk_space_unavailable"))
    return issues


def collect_operations_issues(
    *,
    api_readiness_url: str,
    vllm_health_url: str,
    backup_dir: Path,
    backup_max_age: timedelta,
    disk_paths: Sequence[Path],
    min_disk_free_bytes: int,
    timeout_seconds: float,
    now: datetime | None = None,
    requester: Callable[..., httpx.Response] = httpx.get,
    disk_usage: Callable[[Path], object] = shutil.disk_usage,
) -> tuple[OperationsIssue, ...]:
    """Collect stable issue codes without retaining endpoints or private data."""

    current_time = _normalise_now(now)
    issues = [
        *_check_api_readiness(
            url=api_readiness_url,
            timeout_seconds=timeout_seconds,
            requester=requester,
        ),
        *_check_vllm(
            url=vllm_health_url,
            timeout_seconds=timeout_seconds,
            requester=requester,
        ),
        *_check_backup(
            backup_dir=backup_dir,
            max_age=backup_max_age,
            now=current_time,
        ),
        *_check_disk_space(
            disk_paths=disk_paths,
            min_free_bytes=min_disk_free_bytes,
            disk_usage=disk_usage,
        ),
    ]
    return tuple(sorted(set(issues)))


def observe_issues(
    state: MonitorState,
    issue_codes: Sequence[str],
    *,
    now: datetime,
) -> MonitorState:
    codes = tuple(sorted(set(issue_codes)))
    current_time = _normalise_now(now)
    if codes == state.observed_issue_codes:
        return state
    return replace(
        state,
        observed_issue_codes=codes,
        observed_since=current_time,
        pending_signature=None,
        pending_retry_key=None,
        pending_created_at=None,
    )


def plan_notification(
    state: MonitorState,
    *,
    now: datetime,
    alert_after: timedelta,
    repeat_after: timedelta,
) -> NotificationPlan | None:
    current_time = _normalise_now(now)
    codes = state.observed_issue_codes
    if codes:
        if codes != state.notified_issue_codes:
            if state.observed_since is None or current_time - state.observed_since < alert_after:
                return None
            return NotificationPlan("alert", codes, f"alert:{','.join(codes)}")
        if (
            state.last_notification_at is not None
            and current_time - state.last_notification_at >= repeat_after
        ):
            return NotificationPlan("reminder", codes, f"reminder:{','.join(codes)}")
        return None
    if state.notified_issue_codes:
        return NotificationPlan("recovery", (), "recovery")
    return None


def prepare_notification(
    state: MonitorState,
    plan: NotificationPlan,
    *,
    now: datetime,
    retry_key_lifetime: timedelta = timedelta(hours=23),
) -> tuple[MonitorState, str]:
    current_time = _normalise_now(now)
    if (
        state.pending_signature == plan.signature
        and state.pending_retry_key
        and state.pending_created_at is not None
        and current_time - state.pending_created_at < retry_key_lifetime
    ):
        return state, state.pending_retry_key
    retry_key = str(uuid.uuid4())
    return (
        replace(
            state,
            pending_signature=plan.signature,
            pending_retry_key=retry_key,
            pending_created_at=current_time,
        ),
        retry_key,
    )


def complete_notification(
    state: MonitorState,
    plan: NotificationPlan,
    *,
    now: datetime,
) -> MonitorState:
    return replace(
        state,
        notified_issue_codes=plan.issue_codes,
        last_notification_at=_normalise_now(now),
        pending_signature=None,
        pending_retry_key=None,
        pending_created_at=None,
    )


def format_notification(
    plan: NotificationPlan,
    *,
    issues: Sequence[OperationsIssue],
    now: datetime,
    timezone_name: str,
) -> str:
    checked_at = (
        _normalise_now(now)
        .astimezone(ZoneInfo(timezone_name))
        .strftime("%Y/%m/%d %H:%M")
    )
    if plan.kind == "recovery":
        return "\n".join(
            [
                "【Small Step 復旧】",
                "監視項目がすべて正常に戻りました。",
                f"確認日時: {checked_at}",
            ]
        )

    heading = (
        "【Small Step 運用警告】"
        if plan.kind == "alert"
        else "【Small Step 運用警告・継続中】"
    )
    issue_by_code = {issue.code: issue.message for issue in issues}
    lines = [heading, *(f"・{issue_by_code[code]}" for code in plan.issue_codes), f"確認日時: {checked_at}"]
    lines.append("この通知に園児・音声・接続情報は含まれていません。")
    return "\n".join(lines)


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    parsed = datetime.fromisoformat(value)
    return _normalise_now(parsed)


def load_monitor_state(path: Path) -> MonitorState:
    if not path.exists():
        return MonitorState()
    if path.is_symlink() or not path.is_file():
        return MonitorState()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("version") != 1:
            return MonitorState()
        return MonitorState(
            observed_issue_codes=tuple(sorted(set(payload.get("observed_issue_codes", [])))),
            observed_since=_parse_datetime(payload.get("observed_since")),
            notified_issue_codes=tuple(sorted(set(payload.get("notified_issue_codes", [])))),
            last_notification_at=_parse_datetime(payload.get("last_notification_at")),
            pending_signature=payload.get("pending_signature"),
            pending_retry_key=payload.get("pending_retry_key"),
            pending_created_at=_parse_datetime(payload.get("pending_created_at")),
        )
    except (AttributeError, OSError, TypeError, ValueError):
        return MonitorState()


def save_monitor_state(path: Path, state: MonitorState) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    payload = {
        "version": 1,
        "observed_issue_codes": list(state.observed_issue_codes),
        "observed_since": state.observed_since.isoformat() if state.observed_since else None,
        "notified_issue_codes": list(state.notified_issue_codes),
        "last_notification_at": (
            state.last_notification_at.isoformat() if state.last_notification_at else None
        ),
        "pending_signature": state.pending_signature,
        "pending_retry_key": state.pending_retry_key,
        "pending_created_at": (
            state.pending_created_at.isoformat() if state.pending_created_at else None
        ),
    }
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            delete=False,
        ) as stream:
            temporary_path = Path(stream.name)
            json.dump(payload, stream, ensure_ascii=True, separators=(",", ":"))
            stream.flush()
            os.fsync(stream.fileno())
        temporary_path.chmod(0o600)
        temporary_path.replace(path)
        temporary_path = None
        path.chmod(0o600)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
