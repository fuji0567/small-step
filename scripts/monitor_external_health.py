"""Check the public VRT endpoint from outside and track one GitHub incident."""

from __future__ import annotations

import argparse
import json
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request, urlopen


INCIDENT_MARKER = "<!-- small-step-external-monitor -->"
LINE_ALERT_SENT_MARKER = "<!-- small-step-line-alert-sent -->"
INCIDENT_TITLE = "[運用監視] Small Step VRTに接続できません"
GITHUB_API_URL = "https://api.github.com"
LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"
UrlOpener = Callable[..., Any]


class ExternalMonitorError(RuntimeError):
    """Raised when monitoring cannot safely determine or record its state."""


def validate_health_url(value: str) -> str:
    parsed = urlsplit(value.strip())
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
    ):
        raise ExternalMonitorError("監視先には認証情報を含まないHTTPS URLを設定してください。")
    return value.strip()


def _read_json_response(response: Any, *, max_bytes: int = 16_384) -> Any:
    body = response.read(max_bytes + 1)
    if len(body) > max_bytes:
        raise ExternalMonitorError("監視応答が大きすぎます。")
    try:
        return json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ExternalMonitorError("監視応答がJSONではありません。") from error


def check_external_health(
    url: str,
    *,
    attempts: int = 3,
    timeout_seconds: float = 10.0,
    retry_delay_seconds: float = 3.0,
    opener: UrlOpener = urlopen,
    sleeper: Callable[[float], None] = time.sleep,
) -> bool:
    """Return true only when the secret-free health contract is confirmed."""

    health_url = validate_health_url(url)
    if attempts < 1:
        raise ExternalMonitorError("監視回数は1回以上にしてください。")
    request = Request(
        health_url,
        headers={"Accept": "application/json", "User-Agent": "small-step-external-monitor/1"},
    )
    for attempt in range(attempts):
        try:
            with opener(request, timeout=timeout_seconds) as response:
                status = getattr(response, "status", response.getcode())
                payload = _read_json_response(response)
            if status == 200 and payload == {"status": "ok"}:
                return True
        except (HTTPError, URLError, TimeoutError, OSError, ExternalMonitorError):
            pass
        if attempt + 1 < attempts:
            sleeper(retry_delay_seconds)
    return False


class GitHubIncidentStore:
    def __init__(
        self,
        *,
        token: str,
        repository: str,
        opener: UrlOpener = urlopen,
    ) -> None:
        if not token:
            raise ExternalMonitorError("GITHUB_TOKENが設定されていません。")
        parts = repository.split("/", maxsplit=1)
        if len(parts) != 2 or not all(parts):
            raise ExternalMonitorError("GITHUB_REPOSITORYの形式が不正です。")
        self.token = token
        self.repository = repository
        self.repository_path = "/".join(quote(part, safe="") for part in parts)
        self.opener = opener

    def _request(self, path: str, *, method: str = "GET", payload: Any = None) -> Any:
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(
            f"{GITHUB_API_URL}{path}",
            data=data,
            method=method,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "User-Agent": "small-step-external-monitor/1",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        try:
            with self.opener(request, timeout=15.0) as response:
                return _read_json_response(response)
        except HTTPError as error:
            raise ExternalMonitorError(f"GitHub APIへの記録に失敗しました（HTTP {error.code}）。") from error
        except (URLError, TimeoutError, OSError) as error:
            raise ExternalMonitorError("GitHub APIへ接続できません。") from error

    def find_open_incident(self) -> dict[str, Any] | None:
        query = urlencode({"state": "open", "per_page": 100})
        issues = self._request(f"/repos/{self.repository_path}/issues?{query}")
        if not isinstance(issues, list):
            raise ExternalMonitorError("GitHub Issue一覧の応答が不正です。")
        for issue in issues:
            if (
                isinstance(issue, dict)
                and issue.get("title") == INCIDENT_TITLE
                and INCIDENT_MARKER in str(issue.get("body") or "")
            ):
                return issue
        return None

    def create_incident(self, *, detected_at: datetime, run_url: str) -> dict[str, Any]:
        body = (
            f"{INCIDENT_MARKER}\n"
            "Small Step VRTの外部ヘルスチェックが3回連続で失敗しました。\n\n"
            f"検知時刻（UTC）: {detected_at.isoformat()}\n"
            f"確認先: [GitHub Actionsの実行結果]({run_url})\n\n"
            "このIssueに園児、音声、接続先URL、認証情報は記録していません。"
        )
        issue = self._request(
            f"/repos/{self.repository_path}/issues",
            method="POST",
            payload={"title": INCIDENT_TITLE, "body": body},
        )
        if not isinstance(issue, dict) or not isinstance(issue.get("number"), int):
            raise ExternalMonitorError("GitHub Issueの作成結果が不正です。")
        return issue

    def update_body(self, issue: dict[str, Any], body: str) -> dict[str, Any]:
        return self._update_issue(issue, {"body": body})

    def close_incident(self, issue: dict[str, Any], *, recovered_at: datetime, run_url: str) -> None:
        number = self._issue_number(issue)
        self._request(
            f"/repos/{self.repository_path}/issues/{number}/comments",
            method="POST",
            payload={
                "body": (
                    "外部ヘルスチェックの復旧を確認しました。\n\n"
                    f"復旧確認時刻（UTC）: {recovered_at.isoformat()}\n"
                    f"確認先: [GitHub Actionsの実行結果]({run_url})"
                )
            },
        )
        self._update_issue(issue, {"state": "closed"})

    def _update_issue(self, issue: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
        updated = self._request(
            f"/repos/{self.repository_path}/issues/{self._issue_number(issue)}",
            method="PATCH",
            payload=payload,
        )
        if not isinstance(updated, dict):
            raise ExternalMonitorError("GitHub Issueの更新結果が不正です。")
        return updated

    @staticmethod
    def _issue_number(issue: dict[str, Any]) -> int:
        number = issue.get("number")
        if not isinstance(number, int):
            raise ExternalMonitorError("GitHub Issue番号が不正です。")
        return number


def send_line_status(
    *,
    token: str,
    recipient: str,
    text: str,
    retry_key: str,
    opener: UrlOpener = urlopen,
) -> bool:
    """Send an optional LINE alert; return false when both settings are absent."""

    if not token and not recipient:
        return False
    if not token or not recipient:
        raise ExternalMonitorError("LINE通知用のGitHub Secretsが片方だけ設定されています。")
    request = Request(
        LINE_PUSH_URL,
        data=json.dumps(
            {"to": recipient, "messages": [{"type": "text", "text": text}]}
        ).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "small-step-external-monitor/1",
            "X-Line-Retry-Key": retry_key,
        },
    )
    try:
        with opener(request, timeout=15.0) as response:
            return 200 <= getattr(response, "status", response.getcode()) < 300
    except HTTPError as error:
        if error.code == 409 and error.headers.get("x-line-accepted-request-id"):
            return True
        raise ExternalMonitorError(f"LINE障害通知に失敗しました（HTTP {error.code}）。") from error
    except (URLError, TimeoutError, OSError) as error:
        raise ExternalMonitorError("LINE障害通知へ接続できません。") from error


def _retry_key(repository: str, issue_number: int, kind: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"small-step:{repository}:{issue_number}:{kind}"))


def _line_text(kind: str) -> str:
    status = (
        "VRTへ接続できません。GitHub Actionsの運用監視を確認してください。"
        if kind == "alert"
        else "VRTへの接続が復旧しました。"
    )
    return f"【Small Step 外部監視】\n{status}\n園児・音声・接続先情報は含まれていません。"


def run() -> int:
    parser = argparse.ArgumentParser(description="Small Step VRTを外部から確認します。")
    parser.add_argument("--check-only", action="store_true", help="IssueとLINEを変更せず確認だけ行います")
    parser.add_argument("--attempts", type=int, default=3, help="異常と判断するまでの確認回数")
    parser.add_argument("--timeout-seconds", type=float, default=10.0)
    parser.add_argument("--retry-delay-seconds", type=float, default=3.0)
    args = parser.parse_args()

    health_url = os.environ.get("SMALL_STEP_EXTERNAL_HEALTH_URL", "")
    healthy = check_external_health(
        health_url,
        attempts=args.attempts,
        timeout_seconds=args.timeout_seconds,
        retry_delay_seconds=args.retry_delay_seconds,
    )
    if args.check_only:
        print("外部監視: 正常" if healthy else "外部監視: 接続できません")
        return 0 if healthy else 1

    repository = os.environ.get("GITHUB_REPOSITORY", "")
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    repository_url_path = "/".join(quote(part, safe="") for part in repository.split("/"))
    run_url = f"https://github.com/{repository_url_path}/actions/runs/{quote(run_id, safe='')}"
    store = GitHubIncidentStore(
        token=os.environ.get("GITHUB_TOKEN", ""),
        repository=repository,
    )
    issue = store.find_open_incident()
    now = datetime.now(timezone.utc)
    line_token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
    line_recipient = os.environ.get("OPERATIONS_ALERT_LINE_USER_ID", "")

    if healthy:
        if issue is not None:
            issue_number = GitHubIncidentStore._issue_number(issue)
            send_line_status(
                token=line_token,
                recipient=line_recipient,
                text=_line_text("recovery"),
                retry_key=_retry_key(repository, issue_number, "recovery"),
            )
            store.close_incident(issue, recovered_at=now, run_url=run_url)
            print("外部監視: 復旧を記録しました")
        else:
            print("外部監視: 正常")
        return 0

    if issue is None:
        issue = store.create_incident(detected_at=now, run_url=run_url)
    issue_number = GitHubIncidentStore._issue_number(issue)
    body = str(issue.get("body") or "")
    if LINE_ALERT_SENT_MARKER not in body:
        line_sent = send_line_status(
            token=line_token,
            recipient=line_recipient,
            text=_line_text("alert"),
            retry_key=_retry_key(repository, issue_number, "alert"),
        )
        if line_sent:
            store.update_body(issue, f"{body}\n{LINE_ALERT_SENT_MARKER}")
    print("外部監視: 接続できません。障害Issueを確認してください。")
    return 1


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except ExternalMonitorError as error:
        raise SystemExit(str(error)) from error
