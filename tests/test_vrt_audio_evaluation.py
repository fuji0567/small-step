from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.models import CloudAudioJobStatus
from app.vrt_audio_evaluation import (
    VrtAudioEvaluationCase,
    build_evaluation_report,
    evaluate_audio_cases,
    load_evaluation_manifest,
    write_evaluation_report,
)
from app.vrt_pipeline_verifier import (
    VrtPipelineVerificationError,
    VrtPipelineVerificationResult,
)


def test_manifest_uses_relative_paths_and_rejects_duplicate_case_ids(tmp_path):
    audio = tmp_path / "private-child-name.wav"
    audio.write_bytes(b"audio")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "case_id": "two-speakers",
                        "audio_path": audio.name,
                        "expected_speaker_count": 2,
                        "expected_candidate": True,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    cases = load_evaluation_manifest(str(manifest))

    assert cases == [
        VrtAudioEvaluationCase(
            case_id="two-speakers",
            audio_path=audio,
            expected_speaker_count=2,
            expected_candidate=True,
        )
    ]

    duplicate_payload = json.loads(manifest.read_text(encoding="utf-8"))
    duplicate_payload["cases"].append(duplicate_payload["cases"][0])
    manifest.write_text(json.dumps(duplicate_payload), encoding="utf-8")
    with pytest.raises(VrtPipelineVerificationError, match="重複"):
        load_evaluation_manifest(str(manifest))


def test_evaluation_report_contains_only_aggregate_results(tmp_path):
    first_audio = tmp_path / "private-first-name.wav"
    second_audio = tmp_path / "private-second-name.wav"
    first_audio.write_bytes(b"first")
    second_audio.write_bytes(b"second")
    cases = [
        VrtAudioEvaluationCase("balanced", first_audio, 2, True),
        VrtAudioEvaluationCase("volume-gap", second_audio, 2, False),
    ]

    class FakeVerifier:
        def __init__(self) -> None:
            self.upload_count = 0
            self.readiness_checked = False
            self.device_checked = False

        def verify_readiness(self) -> None:
            self.readiness_checked = True

        def verify_device(self) -> None:
            self.device_checked = True

        def upload(self, *, audio_path: Path, child_id: str | None):
            assert audio_path in {first_audio, second_audio}
            assert child_id is None
            self.upload_count += 1
            return VrtPipelineVerificationResult(
                job_id=f"00000000-0000-4000-8000-00000000000{self.upload_count}",
                status=CloudAudioJobStatus.queued,
                record_id=None,
            )

        def wait_for_completion(self, initial, *, timeout_seconds, poll_seconds, on_status=None):
            assert timeout_seconds == 30
            assert poll_seconds == 1
            if initial.job_id.endswith("1"):
                return VrtPipelineVerificationResult(
                    job_id=initial.job_id,
                    status=CloudAudioJobStatus.completed,
                    record_id="11111111-1111-4111-8111-111111111111",
                    detected_speaker_count=2,
                    used_low_volume_retry=False,
                )
            return VrtPipelineVerificationResult(
                job_id=initial.job_id,
                status=CloudAudioJobStatus.completed,
                record_id=None,
                detected_speaker_count=1,
                used_low_volume_retry=True,
            )

    verifier = FakeVerifier()
    clock = iter((10.0, 12.5, 20.0, 24.0))
    results = evaluate_audio_cases(
        verifier=verifier,
        cases=cases,
        max_file_bytes=100,
        timeout_seconds=30,
        poll_seconds=1,
        monotonic=lambda: next(clock),
    )
    report = build_evaluation_report(results)
    report_path = write_evaluation_report(str(tmp_path / "report.json"), report)
    serialized = report_path.read_text(encoding="utf-8")

    assert verifier.readiness_checked is True
    assert verifier.device_checked is True
    assert report["summary"] == {
        "total": 2,
        "passed": 1,
        "failed": 1,
        "speaker_count_accuracy": 0.5,
        "candidate_accuracy": 1.0,
    }
    assert report["cases"][0]["elapsed_seconds"] == 2.5
    assert report["cases"][1]["used_low_volume_retry"] is True
    assert "private-first-name" not in serialized
    assert "private-second-name" not in serialized
    assert "11111111-1111-4111-8111-111111111111" not in serialized


def test_evaluation_continues_when_one_audio_file_is_missing(tmp_path):
    available_audio = tmp_path / "available.wav"
    available_audio.write_bytes(b"audio")
    cases = [
        VrtAudioEvaluationCase("missing", tmp_path / "missing.wav", 1, False),
        VrtAudioEvaluationCase("available", available_audio, 1, False),
    ]

    class FakeVerifier:
        def verify_readiness(self) -> None:
            pass

        def verify_device(self) -> None:
            pass

        def upload(self, *, audio_path: Path, child_id: str | None):
            return VrtPipelineVerificationResult(
                job_id="00000000-0000-4000-8000-000000000001",
                status=CloudAudioJobStatus.completed,
                record_id=None,
                detected_speaker_count=1,
                used_low_volume_retry=False,
            )

        def wait_for_completion(self, initial, *, timeout_seconds, poll_seconds, on_status=None):
            return initial

    clock = iter((1.0, 1.1, 2.0, 2.5))
    results = evaluate_audio_cases(
        verifier=FakeVerifier(),
        cases=cases,
        max_file_bytes=100,
        timeout_seconds=30,
        poll_seconds=1,
        monotonic=lambda: next(clock),
    )

    assert results[0].status == "verification_error"
    assert results[0].passed is False
    assert results[1].status == "completed"
    assert results[1].passed is True
