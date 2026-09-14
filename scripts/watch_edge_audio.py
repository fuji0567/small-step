"""Process complete recordings locally or hand them to the opt-in VRT worker."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path
import time
from typing import Callable

from app.config import Settings
from app.edge_audio import (
    CloudAudioUploader,
    EdgeAudioError,
    EdgeAudioProcessor,
    EdgeDeviceHeartbeatClient,
    find_ready_audio_files,
)


def positive_float(value: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("0より大きい数値を指定してください。")
    return parsed


def nonnegative_float(value: str) -> float:
    parsed = float(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("0以上の数値を指定してください。")
    return parsed


@dataclass
class RetrySchedule:
    """Track cloud-upload retry delays without recording audio paths or contents."""

    initial_seconds: float
    max_seconds: float
    _failure_counts: dict[tuple[Path, int, int], int] = field(default_factory=dict)
    _next_attempts: dict[tuple[Path, int, int], float] = field(default_factory=dict)

    def is_due(self, file_version: tuple[Path, int, int], *, now: float) -> bool:
        return now >= self._next_attempts.get(file_version, float("-inf"))

    def record_failure(self, file_version: tuple[Path, int, int], *, now: float) -> float:
        failures = self._failure_counts.get(file_version, 0) + 1
        self._failure_counts[file_version] = failures
        delay = min(self.initial_seconds * (2 ** (failures - 1)), self.max_seconds)
        self._next_attempts[file_version] = now + delay
        return delay

    def clear(self, file_version: tuple[Path, int, int]) -> None:
        self._failure_counts.pop(file_version, None)
        self._next_attempts.pop(file_version, None)


def process_ready_audio_files(
    *,
    inbox_dir: str,
    submit_audio_file: Callable[[str, str | None], str | None],
    success_message: str,
    child_id: str | None,
    min_age_seconds: float,
    retry_on_failure: bool = False,
    processed_file_versions: set[tuple[Path, int, int]] | None = None,
    retry_schedule: RetrySchedule | None = None,
    now_monotonic: float | None = None,
) -> int:
    """Submit each ready local file once and return the number accepted."""

    audio_files = find_ready_audio_files(
        inbox_dir=inbox_dir,
        min_age_seconds=min_age_seconds,
    )
    current_time = time.monotonic() if now_monotonic is None else now_monotonic
    submitted_count = 0
    for audio_path in audio_files:
        try:
            stat = audio_path.stat()
        except FileNotFoundError:
            continue
        file_version = (audio_path, stat.st_mtime_ns, stat.st_size)
        if processed_file_versions is not None and file_version in processed_file_versions:
            continue
        if retry_on_failure and retry_schedule is not None and not retry_schedule.is_due(
            file_version, now=current_time
        ):
            continue
        try:
            submitted_id = submit_audio_file(str(audio_path), child_id)
        except EdgeAudioError as error:
            # Do not print paths: filenames can themselves contain personal information.
            print(f"音声の処理に失敗しました: {error}")
            if retry_on_failure and retry_schedule is not None:
                retry_schedule.record_failure(file_version, now=current_time)
            if processed_file_versions is not None and not retry_on_failure:
                processed_file_versions.add(file_version)
            continue
        if retry_schedule is not None:
            retry_schedule.clear(file_version)
        if processed_file_versions is not None:
            processed_file_versions.add(file_version)
        if submitted_id is None:
            print("記録対象の出来事がないため、レビュー候補を作成しませんでした。")
        else:
            submitted_count += 1
            print(f"{success_message}: {submitted_id}")
    return submitted_count


def require_local_ready_configuration(processor: EdgeAudioProcessor) -> None:
    if not processor.status()["llm_configured"]:
        raise SystemExit("LLM_BASE_URL と LLM_MODEL を .env に設定してください。")
    if not processor.status()["edge_api_configured"]:
        raise SystemExit("EDGE_API_URL と EDGE_API_KEY を .env に設定してください。")


def require_cloud_ready_configuration(uploader: CloudAudioUploader) -> None:
    if not uploader.status()["edge_api_configured"]:
        raise SystemExit("EDGE_API_URL と EDGE_API_KEY を .env に設定してください。")


def main() -> None:
    settings = Settings()
    parser = argparse.ArgumentParser(
        description="録音をローカル処理またはVRTの音声処理へ送信します。"
    )
    parser.add_argument(
        "--child-id",
        help="テストでだけ紐付ける園児ID。省略時は先生が確認画面で対象園児を選びます。",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="今ある音声だけを処理して終了します。",
    )
    parser.add_argument(
        "--poll-seconds",
        type=positive_float,
        default=settings.edge_audio_watch_poll_seconds,
        help="監視間隔（秒）。既定値は .env の EDGE_AUDIO_WATCH_POLL_SECONDS です。",
    )
    parser.add_argument(
        "--min-age-seconds",
        type=nonnegative_float,
        default=settings.edge_audio_watch_min_age_seconds,
        help="作成後に待つ秒数。録音中のファイルを避けます。",
    )
    parser.add_argument(
        "--heartbeat-seconds",
        type=positive_float,
        default=settings.edge_device_heartbeat_interval_seconds,
        help="端末の稼働通知の間隔（秒）。既定値は .env の EDGE_DEVICE_HEARTBEAT_INTERVAL_SECONDS です。",
    )
    args = parser.parse_args()

    if settings.edge_audio_processing_mode == "cloud":
        uploader = CloudAudioUploader(settings=settings)
        require_cloud_ready_configuration(uploader)
        inbox_dir = settings.edge_audio_inbox_dir
        submit_audio_file = lambda audio_path, child_id: uploader.submit_audio_file(
            audio_path=audio_path,
            child_id=child_id,
        ).job_id
        success_message = "クラウド音声処理を受け付けました"
        mode_message = "VRTへ送信"
        retry_on_failure = True
    else:
        processor = EdgeAudioProcessor(settings=settings)
        require_local_ready_configuration(processor)
        inbox_dir = settings.edge_audio_inbox_dir
        submit_audio_file = lambda audio_path, child_id: processor.submit_analyzed_audio_file(
            audio_path=audio_path,
            child_id=child_id,
        ).record_id
        success_message = "承認待ちの記録を送信しました"
        mode_message = "ローカル処理"
        retry_on_failure = False
    heartbeat_client = EdgeDeviceHeartbeatClient(settings=settings)
    if args.once:
        print(f"現在ある音声を一度だけ処理します（{mode_message}）。")
    else:
        print("音声フォルダを監視します。終了するには Control+C を押してください。")
    processed_file_versions: set[tuple[Path, int, int]] = set()
    retry_schedule = RetrySchedule(
        initial_seconds=settings.edge_audio_retry_initial_seconds,
        max_seconds=max(settings.edge_audio_retry_initial_seconds, settings.edge_audio_retry_max_seconds),
    )
    last_heartbeat_attempt = float("-inf")

    try:
        while True:
            now = time.monotonic()
            if now - last_heartbeat_attempt >= args.heartbeat_seconds:
                last_heartbeat_attempt = now
                try:
                    heartbeat_client.send()
                except EdgeAudioError as error:
                    print(f"端末の稼働通知に失敗しました: {error}")
                else:
                    if args.once:
                        print("録音端末の稼働通知を送信しました。")
            process_ready_audio_files(
                inbox_dir=inbox_dir,
                submit_audio_file=submit_audio_file,
                success_message=success_message,
                child_id=args.child_id,
                min_age_seconds=args.min_age_seconds,
                retry_on_failure=retry_on_failure,
                processed_file_versions=processed_file_versions,
                retry_schedule=retry_schedule if retry_on_failure else None,
            )
            if args.once:
                return
            time.sleep(args.poll_seconds)
    except KeyboardInterrupt:
        print("音声フォルダの監視を終了しました。")


if __name__ == "__main__":
    main()
