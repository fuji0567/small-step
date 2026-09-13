"""Repeatable, privacy-preserving evaluation of VRT audio samples."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import time
from typing import Callable, Protocol

from app.models import CloudAudioJobStatus
from app.vrt_pipeline_verifier import (
    VrtPipelineVerificationError,
    VrtPipelineVerificationResult,
    validate_verification_audio,
)


CASE_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
MAX_EVALUATION_CASES = 100


class EvaluationVerifier(Protocol):
    def verify_readiness(self) -> None: ...

    def verify_device(self) -> None: ...

    def upload(self, *, audio_path: Path, child_id: str | None) -> VrtPipelineVerificationResult: ...

    def wait_for_completion(
        self,
        initial: VrtPipelineVerificationResult,
        *,
        timeout_seconds: float,
        poll_seconds: float,
        on_status: Callable[[CloudAudioJobStatus], None] | None = None,
    ) -> VrtPipelineVerificationResult: ...


@dataclass(frozen=True)
class VrtAudioEvaluationCase:
    """One local sample identified only by a non-personal test ID."""

    case_id: str
    audio_path: Path
    expected_speaker_count: int
    expected_candidate: bool


@dataclass(frozen=True)
class VrtAudioEvaluationResult:
    """Aggregate-only result safe to save outside the raw-audio directory."""

    case_id: str
    status: str
    expected_speaker_count: int
    detected_speaker_count: int | None
    expected_candidate: bool
    candidate_created: bool | None
    used_low_volume_retry: bool | None
    elapsed_seconds: float
    processing_completed: bool
    speaker_count_matches: bool
    candidate_matches: bool

    @property
    def passed(self) -> bool:
        return self.processing_completed and self.speaker_count_matches and self.candidate_matches

    def as_dict(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "status": self.status,
            "expected_speaker_count": self.expected_speaker_count,
            "detected_speaker_count": self.detected_speaker_count,
            "expected_candidate": self.expected_candidate,
            "candidate_created": self.candidate_created,
            "used_low_volume_retry": self.used_low_volume_retry,
            "elapsed_seconds": round(self.elapsed_seconds, 3),
            "processing_completed": self.processing_completed,
            "speaker_count_matches": self.speaker_count_matches,
            "candidate_matches": self.candidate_matches,
            "passed": self.passed,
        }


def load_evaluation_manifest(path: str) -> list[VrtAudioEvaluationCase]:
    """Load a bounded manifest without copying filenames into any result."""

    manifest_path = Path(path).expanduser().resolve()
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise VrtPipelineVerificationError("評価用マニフェストを読み取れませんでした。") from error
    if not isinstance(payload, dict) or set(payload) != {"cases"} or not isinstance(payload["cases"], list):
        raise VrtPipelineVerificationError("評価用マニフェストはcases配列だけを含むJSONにしてください。")
    if not payload["cases"] or len(payload["cases"]) > MAX_EVALUATION_CASES:
        raise VrtPipelineVerificationError("評価ケースは1件以上100件以下にしてください。")

    cases: list[VrtAudioEvaluationCase] = []
    seen_ids: set[str] = set()
    required_fields = {
        "case_id",
        "audio_path",
        "expected_speaker_count",
        "expected_candidate",
    }
    for item in payload["cases"]:
        if not isinstance(item, dict) or set(item) != required_fields:
            raise VrtPipelineVerificationError("各評価ケースの項目が正しくありません。")
        case_id = item["case_id"]
        audio_path = item["audio_path"]
        expected_speaker_count = item["expected_speaker_count"]
        expected_candidate = item["expected_candidate"]
        if not isinstance(case_id, str) or not CASE_ID_PATTERN.fullmatch(case_id):
            raise VrtPipelineVerificationError(
                "case_idは英小文字・数字・ハイフン・アンダースコアで指定してください。"
            )
        if case_id in seen_ids:
            raise VrtPipelineVerificationError("case_idが重複しています。")
        if not isinstance(audio_path, str) or not audio_path:
            raise VrtPipelineVerificationError("audio_pathを指定してください。")
        if (
            isinstance(expected_speaker_count, bool)
            or not isinstance(expected_speaker_count, int)
            or not 0 <= expected_speaker_count <= 20
        ):
            raise VrtPipelineVerificationError("expected_speaker_countは0から20の整数にしてください。")
        if not isinstance(expected_candidate, bool):
            raise VrtPipelineVerificationError("expected_candidateはtrueまたはfalseにしてください。")
        seen_ids.add(case_id)
        cases.append(
            VrtAudioEvaluationCase(
                case_id=case_id,
                audio_path=(manifest_path.parent / audio_path).resolve(),
                expected_speaker_count=expected_speaker_count,
                expected_candidate=expected_candidate,
            )
        )
    return cases


def evaluate_audio_cases(
    *,
    verifier: EvaluationVerifier,
    cases: list[VrtAudioEvaluationCase],
    max_file_bytes: int,
    timeout_seconds: float,
    poll_seconds: float,
    monotonic: Callable[[], float] = time.monotonic,
    on_case_start: Callable[[int, int, str], None] | None = None,
) -> list[VrtAudioEvaluationResult]:
    """Evaluate samples sequentially so one GPU worker remains predictable."""

    verifier.verify_readiness()
    verifier.verify_device()
    results: list[VrtAudioEvaluationResult] = []
    for index, case in enumerate(cases, start=1):
        if on_case_start is not None:
            on_case_start(index, len(cases), case.case_id)
        started_at = monotonic()
        try:
            audio_path = validate_verification_audio(
                str(case.audio_path),
                max_file_bytes=max_file_bytes,
            )
            initial = verifier.upload(audio_path=audio_path, child_id=None)
            completed = verifier.wait_for_completion(
                initial,
                timeout_seconds=timeout_seconds,
                poll_seconds=poll_seconds,
            )
        except VrtPipelineVerificationError:
            results.append(
                VrtAudioEvaluationResult(
                    case_id=case.case_id,
                    status="verification_error",
                    expected_speaker_count=case.expected_speaker_count,
                    detected_speaker_count=None,
                    expected_candidate=case.expected_candidate,
                    candidate_created=None,
                    used_low_volume_retry=None,
                    elapsed_seconds=monotonic() - started_at,
                    processing_completed=False,
                    speaker_count_matches=False,
                    candidate_matches=False,
                )
            )
            continue

        processing_completed = completed.status == CloudAudioJobStatus.completed
        candidate_created = completed.created_candidate if processing_completed else None
        results.append(
            VrtAudioEvaluationResult(
                case_id=case.case_id,
                status=completed.status.value,
                expected_speaker_count=case.expected_speaker_count,
                detected_speaker_count=completed.detected_speaker_count,
                expected_candidate=case.expected_candidate,
                candidate_created=candidate_created,
                used_low_volume_retry=completed.used_low_volume_retry,
                elapsed_seconds=monotonic() - started_at,
                processing_completed=processing_completed,
                speaker_count_matches=(
                    completed.detected_speaker_count == case.expected_speaker_count
                ),
                candidate_matches=(candidate_created == case.expected_candidate),
            )
        )
    return results


def build_evaluation_report(results: list[VrtAudioEvaluationResult]) -> dict[str, object]:
    """Build a report that contains no paths, transcripts, names, or job IDs."""

    total = len(results)
    passed = sum(result.passed for result in results)
    speaker_matches = sum(result.speaker_count_matches for result in results)
    candidate_matches = sum(result.candidate_matches for result in results)
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total": total,
            "passed": passed,
            "failed": total - passed,
            "speaker_count_accuracy": round(speaker_matches / total, 3) if total else 0.0,
            "candidate_accuracy": round(candidate_matches / total, 3) if total else 0.0,
        },
        "cases": [result.as_dict() for result in results],
    }


def write_evaluation_report(path: str, report: dict[str, object]) -> Path:
    """Write aggregate metrics atomically without ever including raw content."""

    output_path = Path(path).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(f"{output_path.suffix}.tmp")
    temporary_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary_path.replace(output_path)
    return output_path
