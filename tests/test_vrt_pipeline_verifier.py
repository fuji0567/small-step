from __future__ import annotations

import httpx
import pytest

from app.models import CloudAudioJobStatus, RecordCategory
from app.vrt_pipeline_verifier import (
    VrtPipelineVerificationError,
    VrtPipelineVerificationResult,
    VrtPipelineVerifier,
    audio_pipeline_is_ready,
    validate_verification_api_url,
    validate_verification_audio,
)


JOB_ID = "11111111-1111-4111-8111-111111111111"
RECORD_ID = "22222222-2222-4222-8222-222222222222"


def test_verifier_allows_https_and_loopback_http_only():
    assert validate_verification_api_url("https://vrt.example.test/") == "https://vrt.example.test"
    assert validate_verification_api_url("http://127.0.0.1:18000") == "http://127.0.0.1:18000"
    with pytest.raises(VrtPipelineVerificationError):
        validate_verification_api_url("http://vrt.example.test")
    with pytest.raises(VrtPipelineVerificationError):
        validate_verification_api_url("https://name:password@vrt.example.test")
    with pytest.raises(VrtPipelineVerificationError):
        validate_verification_api_url("https://vrt.example.test/api/v1")


def test_verifier_rejects_empty_and_unsupported_audio(tmp_path):
    empty = tmp_path / "empty.wav"
    empty.touch()
    unsupported = tmp_path / "audio.txt"
    unsupported.write_text("audio", encoding="ascii")

    with pytest.raises(VrtPipelineVerificationError, match="空"):
        validate_verification_audio(str(empty), max_file_bytes=100)
    with pytest.raises(VrtPipelineVerificationError, match="対応していない"):
        validate_verification_audio(str(unsupported), max_file_bytes=100)


def test_audio_readiness_ignores_unrelated_line_worker_state():
    payload = {
        "database_ready": True,
        "database_migration_current": True,
        "cloud_audio_enabled": True,
        "cloud_audio_job_storage_ready": True,
        "cloud_audio_llm_configured": True,
        "cloud_audio_worker_ready": True,
        "line_delivery_configured": True,
        "line_delivery_worker_ready": False,
    }

    assert audio_pipeline_is_ready(payload) is True
    payload["cloud_audio_worker_ready"] = False
    assert audio_pipeline_is_ready(payload) is False


def test_verifier_uploads_anonymous_filename_and_waits_for_candidate(tmp_path):
    audio = tmp_path / "private-child-name.wav"
    audio.write_bytes(b"RIFF-private-audio")
    states = iter(("processing", "completed"))
    requests: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append((request.method, request.url.path))
        if request.url.path == "/api/v1/readiness":
            assert "X-Edge-Api-Key" not in request.headers
            return httpx.Response(
                200,
                json={
                    "database_ready": True,
                    "database_migration_current": True,
                    "cloud_audio_enabled": True,
                    "cloud_audio_job_storage_ready": True,
                    "cloud_audio_llm_configured": True,
                    "cloud_audio_worker_ready": True,
                },
            )
        assert request.headers["X-Edge-Api-Key"] == "edge-secret"
        if request.url.path == "/api/v1/edge/me":
            return httpx.Response(200, json={})
        if request.method == "POST":
            body = request.read()
            assert b'filename="audio.wav"' in body
            assert b"private-child-name" not in body
            assert request.headers["X-Edge-Upload-Id"]
            return httpx.Response(201, json={"id": JOB_ID, "status": "queued", "record_id": None})
        status = next(states)
        return httpx.Response(
            200,
            json={
                "id": JOB_ID,
                "status": status,
                "record_id": RECORD_ID if status == "completed" else None,
                "detected_speaker_count": 2 if status == "completed" else None,
                "used_low_volume_retry": status == "completed",
                "candidate_category": "growth" if status == "completed" else None,
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    verifier = VrtPipelineVerifier(
        api_url="https://vrt.example.test",
        api_key="edge-secret",
        request_timeout_seconds=15,
        client=client,
        sleep=lambda _seconds: None,
    )
    statuses: list[CloudAudioJobStatus] = []

    verifier.verify_readiness()
    verifier.verify_device()
    initial = verifier.upload(audio_path=audio, child_id=None)
    result = verifier.wait_for_completion(
        initial,
        timeout_seconds=10,
        poll_seconds=1,
        on_status=statuses.append,
    )

    assert result.created_candidate is True
    assert result.detected_speaker_count == 2
    assert result.used_low_volume_retry is True
    assert result.candidate_category == RecordCategory.growth
    assert statuses == [
        CloudAudioJobStatus.queued,
        CloudAudioJobStatus.processing,
        CloudAudioJobStatus.completed,
    ]
    assert audio.exists()
    assert requests[-1] == ("GET", f"/api/v1/edge/audio-jobs/{JOB_ID}")


def test_verifier_rejects_invalid_quality_metrics(tmp_path):
    audio = tmp_path / "sample.wav"
    audio.write_bytes(b"audio")

    verifier = VrtPipelineVerifier(
        api_url="https://vrt.example.test",
        api_key="edge-secret",
        request_timeout_seconds=15,
        client=httpx.Client(
            transport=httpx.MockTransport(
                lambda _request: httpx.Response(
                    201,
                    json={
                        "id": JOB_ID,
                        "status": "completed",
                        "record_id": None,
                        "detected_speaker_count": "two",
                    },
                )
            )
        ),
    )

    with pytest.raises(VrtPipelineVerificationError, match="不正"):
        verifier.upload(audio_path=audio, child_id=None)

    verifier.client = httpx.Client(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                201,
                json={
                    "id": JOB_ID,
                    "status": "completed",
                    "record_id": RECORD_ID,
                    "candidate_category": "unknown",
                },
            )
        )
    )
    with pytest.raises(VrtPipelineVerificationError, match="不正"):
        verifier.upload(audio_path=audio, child_id=None)


def test_verifier_reports_completed_non_record_as_success(tmp_path):
    audio = tmp_path / "quiet.wav"
    audio.write_bytes(b"quiet")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(201, json={"id": JOB_ID, "status": "completed", "record_id": None})
        raise AssertionError("A completed upload must not be polled")

    verifier = VrtPipelineVerifier(
        api_url="https://vrt.example.test",
        api_key="edge-secret",
        request_timeout_seconds=15,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    initial = verifier.upload(audio_path=audio, child_id=None)
    result = verifier.wait_for_completion(initial, timeout_seconds=10, poll_seconds=1)

    assert result.status == CloudAudioJobStatus.completed
    assert result.created_candidate is False


def test_verifier_timeout_does_not_claim_the_job_failed():
    clock = [0.0]

    def monotonic() -> float:
        return clock[0]

    def sleep(seconds: float) -> None:
        clock[0] += seconds

    verifier = VrtPipelineVerifier(
        api_url="https://vrt.example.test",
        api_key="edge-secret",
        request_timeout_seconds=15,
        client=httpx.Client(transport=httpx.MockTransport(lambda _request: httpx.Response(500))),
        sleep=sleep,
        monotonic=monotonic,
    )
    initial = VrtPipelineVerificationResult(
        job_id=JOB_ID,
        status=CloudAudioJobStatus.queued,
        record_id=None,
    )

    with pytest.raises(VrtPipelineVerificationError, match="処理を継続"):
        verifier.wait_for_completion(initial, timeout_seconds=1, poll_seconds=1)
