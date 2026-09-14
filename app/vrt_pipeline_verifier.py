"""Safe end-to-end verification for the VRT cloud-audio pipeline."""

from __future__ import annotations

from dataclasses import dataclass
import ipaddress
from pathlib import Path
import time
from typing import Callable
from urllib.parse import urlparse
from uuid import UUID, uuid4

import httpx

from app.edge_audio import EdgeAudioError, audio_media_type, resolve_audio_path
from app.models import CloudAudioJobStatus, RecordCategory


class VrtPipelineVerificationError(RuntimeError):
    """Raised when a safe VRT smoke test cannot finish."""


@dataclass(frozen=True)
class VrtPipelineVerificationResult:
    """Secret-free result of one uploaded test recording."""

    job_id: str
    status: CloudAudioJobStatus
    record_id: str | None
    detected_speaker_count: int | None = None
    used_low_volume_retry: bool | None = None
    candidate_category: RecordCategory | None = None

    @property
    def created_candidate(self) -> bool:
        return self.status == CloudAudioJobStatus.completed and self.record_id is not None


def validate_verification_api_url(api_url: str) -> str:
    """Allow HTTPS and loopback HTTP used through the local SSH tunnel."""

    parsed = urlparse(api_url)
    if (
        not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise VrtPipelineVerificationError("API URLの形式が正しくありません。")
    is_loopback = parsed.hostname == "localhost"
    try:
        is_loopback = is_loopback or ipaddress.ip_address(parsed.hostname).is_loopback
    except ValueError:
        pass
    if parsed.scheme != "https" and not (parsed.scheme == "http" and is_loopback):
        raise VrtPipelineVerificationError(
            "外部のAPI URLにはHTTPSが必要です。SSH転送中の127.0.0.1だけHTTPを使用できます。"
        )
    return api_url.rstrip("/")


def validate_verification_audio(audio_path: str, *, max_file_bytes: int) -> Path:
    try:
        resolved = resolve_audio_path(
            audio_path=audio_path,
            inbox_dir=".",
            max_file_bytes=max_file_bytes,
            require_inbox=False,
        )
    except EdgeAudioError as error:
        messages = {
            "Audio file was not found": "音声ファイルが見つかりません。",
            "Unsupported audio format": (
                "対応していない音声形式です。WAV、MP3、M4A、OGG、FLACを使用してください。"
            ),
            "Audio file exceeds EDGE_AUDIO_MAX_FILE_BYTES": (
                "音声ファイルがアップロード可能な上限を超えています。"
            ),
        }
        raise VrtPipelineVerificationError(
            messages.get(str(error), "音声ファイルを安全に確認できませんでした。")
        ) from error
    if resolved.stat().st_size == 0:
        raise VrtPipelineVerificationError("音声ファイルが空です。")
    return resolved


def audio_pipeline_is_ready(payload: object) -> bool:
    if not isinstance(payload, dict):
        return False
    return all(
        payload.get(field) is True
        for field in (
            "database_ready",
            "database_migration_current",
            "cloud_audio_enabled",
            "cloud_audio_job_storage_ready",
            "cloud_audio_llm_configured",
            "cloud_audio_worker_ready",
        )
    )


def _job_result(payload: object) -> VrtPipelineVerificationResult:
    if not isinstance(payload, dict):
        raise VrtPipelineVerificationError("VRTから不正な処理状態が返されました。")
    try:
        job_id = str(UUID(str(payload["id"])))
        status = CloudAudioJobStatus(payload["status"])
        raw_record_id = payload.get("record_id")
        record_id = str(UUID(str(raw_record_id))) if raw_record_id is not None else None
        detected_speaker_count = payload.get("detected_speaker_count")
        if detected_speaker_count is not None and (
            isinstance(detected_speaker_count, bool)
            or not isinstance(detected_speaker_count, int)
            or detected_speaker_count < 0
        ):
            raise ValueError("invalid detected speaker count")
        used_low_volume_retry = payload.get("used_low_volume_retry")
        if used_low_volume_retry is not None and not isinstance(used_low_volume_retry, bool):
            raise ValueError("invalid low-volume retry state")
        raw_candidate_category = payload.get("candidate_category")
        candidate_category = (
            RecordCategory(raw_candidate_category)
            if raw_candidate_category is not None
            else None
        )
        if record_id is None and candidate_category is not None:
            raise ValueError("non-candidate job cannot have a category")
    except (KeyError, TypeError, ValueError) as error:
        raise VrtPipelineVerificationError("VRTから不正な処理状態が返されました。") from error
    return VrtPipelineVerificationResult(
        job_id=job_id,
        status=status,
        record_id=record_id,
        detected_speaker_count=detected_speaker_count,
        used_low_volume_retry=used_low_volume_retry,
        candidate_category=candidate_category,
    )


class VrtPipelineVerifier:
    """Upload one recording and wait only as far as teacher review."""

    def __init__(
        self,
        *,
        api_url: str,
        api_key: str,
        request_timeout_seconds: float,
        client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        if not api_key:
            raise VrtPipelineVerificationError("録音端末キーを入力してください。")
        if request_timeout_seconds <= 0:
            raise VrtPipelineVerificationError("通信の待機時間は0より大きい値を指定してください。")
        self.api_url = validate_verification_api_url(api_url)
        self.api_key = api_key
        self.request_timeout_seconds = request_timeout_seconds
        self.client = client or httpx.Client()
        self._owns_client = client is None
        self.sleep = sleep
        self.monotonic = monotonic

    @property
    def edge_headers(self) -> dict[str, str]:
        return {"X-Edge-Api-Key": self.api_key}

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def verify_readiness(self) -> None:
        try:
            response = self.client.get(
                f"{self.api_url}/api/v1/readiness",
                timeout=self.request_timeout_seconds,
            )
            payload = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise VrtPipelineVerificationError(
                "VRTの稼働状態を確認できませんでした。APIとSSH転送またはHTTPS URLを確認してください。"
            ) from error
        if not audio_pipeline_is_ready(payload):
            raise VrtPipelineVerificationError(
                "VRTのGPU音声処理はまだ準備完了ではありません。"
                "先生画面の「稼働準備」でGPU音声処理まで確認してください。"
            )

    def verify_device(self) -> None:
        try:
            response = self.client.get(
                f"{self.api_url}/api/v1/edge/me",
                headers=self.edge_headers,
                timeout=self.request_timeout_seconds,
            )
        except httpx.HTTPError as error:
            raise VrtPipelineVerificationError("録音端末キーをVRTで確認できませんでした。") from error
        if response.status_code != 200:
            raise VrtPipelineVerificationError(
                "録音端末キーが無効です。先生画面で端末の状態を確認してください。"
            )

    def upload(self, *, audio_path: Path, child_id: str | None) -> VrtPipelineVerificationResult:
        safe_child_id: str | None = None
        if child_id:
            try:
                safe_child_id = str(UUID(child_id))
            except ValueError as error:
                raise VrtPipelineVerificationError("園児IDはUUID形式で指定してください。") from error

        upload_id = str(uuid4())
        headers = {**self.edge_headers, "X-Edge-Upload-Id": upload_id}
        form = {"child_id": safe_child_id} if safe_child_id else None
        try:
            with audio_path.open("rb") as stream:
                response = self.client.post(
                    f"{self.api_url}/api/v1/edge/audio-jobs",
                    headers=headers,
                    data=form,
                    files={
                        "audio": (
                            f"audio{audio_path.suffix.lower()}",
                            stream,
                            audio_media_type(audio_path),
                        )
                    },
                    timeout=self.request_timeout_seconds,
                )
        except (OSError, httpx.HTTPError) as error:
            raise VrtPipelineVerificationError(
                "音声をVRTへアップロードできませんでした。元の音声は削除していません。"
            ) from error
        if response.status_code != 201:
            raise VrtPipelineVerificationError(
                f"VRTが音声を受け付けませんでした（HTTP {response.status_code}）。"
            )
        try:
            return _job_result(response.json())
        except ValueError as error:
            raise VrtPipelineVerificationError("VRTの受付応答を確認できませんでした。") from error

    def wait_for_completion(
        self,
        initial: VrtPipelineVerificationResult,
        *,
        timeout_seconds: float,
        poll_seconds: float,
        on_status: Callable[[CloudAudioJobStatus], None] | None = None,
    ) -> VrtPipelineVerificationResult:
        if timeout_seconds <= 0 or poll_seconds <= 0:
            raise VrtPipelineVerificationError("待機時間は0より大きい値を指定してください。")
        deadline = self.monotonic() + timeout_seconds
        current = initial
        last_reported: CloudAudioJobStatus | None = None
        terminal = {
            CloudAudioJobStatus.completed,
            CloudAudioJobStatus.failed,
            CloudAudioJobStatus.expired,
        }
        while True:
            if on_status is not None and current.status != last_reported:
                on_status(current.status)
                last_reported = current.status
            if current.status in terminal:
                return current
            if self.monotonic() >= deadline:
                raise VrtPipelineVerificationError(
                    "待機時間内にGPU処理が完了しませんでした。ジョブはVRT上で処理を継続しています。"
                )
            self.sleep(poll_seconds)
            if self.monotonic() >= deadline:
                raise VrtPipelineVerificationError(
                    "待機時間内にGPU処理が完了しませんでした。ジョブはVRT上で処理を継続しています。"
                )
            try:
                response = self.client.get(
                    f"{self.api_url}/api/v1/edge/audio-jobs/{current.job_id}",
                    headers=self.edge_headers,
                    timeout=self.request_timeout_seconds,
                )
            except httpx.HTTPError as error:
                raise VrtPipelineVerificationError(
                    "GPU処理状態を確認できませんでした。ジョブはVRT上で処理を継続している可能性があります。"
                ) from error
            if response.status_code != 200:
                raise VrtPipelineVerificationError(
                    f"GPU処理状態を取得できませんでした（HTTP {response.status_code}）。"
                )
            try:
                current = _job_result(response.json())
            except ValueError as error:
                raise VrtPipelineVerificationError("GPU処理状態を読み取れませんでした。") from error
