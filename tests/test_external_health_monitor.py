import io
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError

import pytest

from scripts.monitor_external_health import (
    ExternalMonitorError,
    GitHubIncidentStore,
    INCIDENT_MARKER,
    INCIDENT_TITLE,
    check_external_health,
    send_line_status,
    validate_health_url,
)


ROOT = Path(__file__).resolve().parents[1]


class FakeResponse:
    def __init__(self, *, status: int, payload: object) -> None:
        self.status = status
        self._body = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self, size: int = -1) -> bytes:
        return self._body[:size]

    def getcode(self) -> int:
        return self.status


def test_external_health_requires_secret_free_https_url():
    assert validate_health_url("https://example.com/api/v1/health").startswith("https://")

    for unsafe_url in (
        "http://example.com/api/v1/health",
        "https://user:password@example.com/health",
        "https://example.com/health#secret",
        "",
    ):
        with pytest.raises(ExternalMonitorError):
            validate_health_url(unsafe_url)


def test_external_health_requires_exact_health_contract():
    def healthy_opener(_request, *, timeout):
        assert timeout == 2.0
        return FakeResponse(status=200, payload={"status": "ok"})

    assert check_external_health(
        "https://example.com/api/v1/health",
        attempts=1,
        timeout_seconds=2.0,
        opener=healthy_opener,
    )

    assert not check_external_health(
        "https://example.com/api/v1/health",
        attempts=1,
        opener=lambda *_args, **_kwargs: FakeResponse(
            status=200,
            payload={"status": "ready", "database": "internal-value"},
        ),
    )


def test_external_health_retries_temporary_failures_without_exposing_response():
    attempts = []
    delays = []

    def opener(request, *, timeout):
        attempts.append((request.full_url, timeout))
        if len(attempts) < 3:
            raise HTTPError(request.full_url, 503, "unavailable", {}, io.BytesIO(b"secret"))
        return FakeResponse(status=200, payload={"status": "ok"})

    assert check_external_health(
        "https://example.com/api/v1/health",
        attempts=3,
        timeout_seconds=4.0,
        retry_delay_seconds=0.5,
        opener=opener,
        sleeper=delays.append,
    )
    assert len(attempts) == 3
    assert delays == [0.5, 0.5]


def test_optional_line_alert_uses_retry_key_and_contains_no_health_url():
    captured = {}

    def opener(request, *, timeout):
        captured["headers"] = dict(request.header_items())
        captured["payload"] = json.loads(request.data)
        captured["timeout"] = timeout
        return FakeResponse(status=200, payload={})

    assert send_line_status(
        token="line-token",
        recipient="operator-id",
        text="VRTへ接続できません。",
        retry_key="63f5c576-b982-47af-985b-25d0f67f0118",
        opener=opener,
    )
    assert captured["payload"] == {
        "to": "operator-id",
        "messages": [{"type": "text", "text": "VRTへ接続できません。"}],
    }
    assert captured["headers"]["X-line-retry-key"] == "63f5c576-b982-47af-985b-25d0f67f0118"
    assert "example.com" not in json.dumps(captured["payload"])


def test_line_alert_requires_both_or_neither_setting():
    assert not send_line_status(token="", recipient="", text="test", retry_key="key")
    with pytest.raises(ExternalMonitorError):
        send_line_status(token="token", recipient="", text="test", retry_key="key")


def test_github_store_finds_only_the_open_external_monitor_incident():
    issues = [
        {"number": 1, "title": "Unrelated issue", "body": INCIDENT_MARKER},
        {"number": 2, "title": INCIDENT_TITLE, "body": "No ownership marker"},
        {"number": 3, "title": INCIDENT_TITLE, "body": INCIDENT_MARKER},
    ]
    store = GitHubIncidentStore(
        token="github-token",
        repository="owner/repository",
        opener=lambda *_args, **_kwargs: FakeResponse(status=200, payload=issues),
    )

    assert store.find_open_incident() == issues[2]


def test_github_incident_contains_no_monitored_url_or_personal_data():
    captured = {}

    def opener(request, *, timeout):
        captured["url"] = request.full_url
        captured["payload"] = json.loads(request.data)
        captured["timeout"] = timeout
        return FakeResponse(status=201, payload={"number": 7})

    store = GitHubIncidentStore(
        token="github-token",
        repository="owner/repository",
        opener=opener,
    )
    issue = store.create_incident(
        detected_at=datetime(2026, 9, 14, tzinfo=timezone.utc),
        run_url="https://github.com/owner/repository/actions/runs/123",
    )

    body = captured["payload"]["body"]
    assert issue == {"number": 7}
    assert captured["url"] == "https://api.github.com/repos/owner/repository/issues"
    assert INCIDENT_MARKER in body
    assert "trycloudflare.com" not in body
    assert "園児名" not in body
    assert "認証情報" in body


def test_external_monitor_workflow_is_disabled_until_configured_and_contains_no_secret():
    workflow = (ROOT / ".github" / "workflows" / "external-vrt-monitor.yml").read_text(
        encoding="utf-8"
    )

    assert 'cron: "*/5 * * * *"' in workflow
    assert "issues: write" in workflow
    assert "vars.SMALL_STEP_EXTERNAL_MONITOR_ENABLED == 'true'" in workflow
    assert "secrets.SMALL_STEP_EXTERNAL_HEALTH_URL" in workflow
    assert "secrets.LINE_CHANNEL_ACCESS_TOKEN" in workflow
    assert "secrets.OPERATIONS_ALERT_LINE_USER_ID" in workflow
    assert "trycloudflare.com" not in workflow
    assert "api.line.me" not in workflow
