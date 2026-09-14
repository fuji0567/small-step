"""Repeatable, privacy-preserving evaluation of VRT audio samples."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
import time
from typing import Callable, Protocol

from app.models import CloudAudioJobStatus, RecordCategory
from app.vrt_pipeline_verifier import (
    VrtPipelineVerificationError,
    VrtPipelineVerificationResult,
    validate_verification_audio,
)


CASE_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
MAX_EVALUATION_CASES = 100
ACCEPTANCE_FIELDS = {
    "min_processing_completion_rate",
    "min_speaker_count_accuracy",
    "min_candidate_accuracy",
    "min_category_accuracy",
    "max_p95_elapsed_seconds",
    "min_summary_approval_rate",
    "min_conversation_prompt_approval_rate",
}


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
    expected_category: RecordCategory | None = None


@dataclass(frozen=True)
class VrtAudioAcceptanceCriteria:
    """Aggregate thresholds that decide whether an evaluation run is usable."""

    min_processing_completion_rate: float = 1.0
    min_speaker_count_accuracy: float = 1.0
    min_candidate_accuracy: float = 1.0
    min_category_accuracy: float | None = None
    max_p95_elapsed_seconds: float | None = None
    min_summary_approval_rate: float | None = None
    min_conversation_prompt_approval_rate: float | None = None


@dataclass(frozen=True)
class VrtAudioEvaluationPlan:
    cases: list[VrtAudioEvaluationCase]
    acceptance: VrtAudioAcceptanceCriteria


@dataclass(frozen=True)
class VrtAudioHumanReview:
    """A teacher's content judgement without retaining generated text."""

    summary_acceptable: bool
    conversation_prompt_acceptable: bool


@dataclass(frozen=True)
class VrtAudioEvaluationResult:
    """Aggregate-only result safe to save outside the raw-audio directory."""

    case_id: str
    status: str
    expected_speaker_count: int
    detected_speaker_count: int | None
    expected_candidate: bool
    candidate_created: bool | None
    expected_category: RecordCategory | None
    candidate_category: RecordCategory | None
    used_low_volume_retry: bool | None
    elapsed_seconds: float
    processing_completed: bool
    speaker_count_matches: bool
    candidate_matches: bool
    category_matches: bool | None
    summary_acceptable: bool | None = None
    conversation_prompt_acceptable: bool | None = None

    @property
    def passed(self) -> bool:
        automated_passed = (
            self.processing_completed
            and self.speaker_count_matches
            and self.candidate_matches
            and self.category_matches is not False
        )
        human_review_passed = (
            self.summary_acceptable is not False
            and self.conversation_prompt_acceptable is not False
        )
        return automated_passed and human_review_passed

    def as_dict(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "status": self.status,
            "expected_speaker_count": self.expected_speaker_count,
            "detected_speaker_count": self.detected_speaker_count,
            "expected_candidate": self.expected_candidate,
            "candidate_created": self.candidate_created,
            "expected_category": (
                self.expected_category.value if self.expected_category is not None else None
            ),
            "candidate_category": (
                self.candidate_category.value if self.candidate_category is not None else None
            ),
            "used_low_volume_retry": self.used_low_volume_retry,
            "elapsed_seconds": round(self.elapsed_seconds, 3),
            "processing_completed": self.processing_completed,
            "speaker_count_matches": self.speaker_count_matches,
            "candidate_matches": self.candidate_matches,
            "category_matches": self.category_matches,
            "summary_acceptable": self.summary_acceptable,
            "conversation_prompt_acceptable": self.conversation_prompt_acceptable,
            "passed": self.passed,
        }


def _optional_rate(value: object, *, field: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1:
        raise VrtPipelineVerificationError(f"{field}は0から1の数値にしてください。")
    return float(value)


def _load_acceptance(payload: object) -> VrtAudioAcceptanceCriteria:
    if payload is None:
        return VrtAudioAcceptanceCriteria()
    if not isinstance(payload, dict) or not set(payload) <= ACCEPTANCE_FIELDS:
        raise VrtPipelineVerificationError("acceptanceの項目が正しくありません。")
    minimums = {
        field: _optional_rate(payload.get(field), field=field)
        for field in ACCEPTANCE_FIELDS
        if field.startswith("min_")
    }
    max_p95 = payload.get("max_p95_elapsed_seconds")
    if max_p95 is not None and (
        isinstance(max_p95, bool) or not isinstance(max_p95, (int, float)) or max_p95 <= 0
    ):
        raise VrtPipelineVerificationError(
            "max_p95_elapsed_secondsは0より大きい数値にしてください。"
        )
    return VrtAudioAcceptanceCriteria(
        min_processing_completion_rate=minimums["min_processing_completion_rate"]
        if minimums["min_processing_completion_rate"] is not None
        else 1.0,
        min_speaker_count_accuracy=minimums["min_speaker_count_accuracy"]
        if minimums["min_speaker_count_accuracy"] is not None
        else 1.0,
        min_candidate_accuracy=minimums["min_candidate_accuracy"]
        if minimums["min_candidate_accuracy"] is not None
        else 1.0,
        min_category_accuracy=minimums["min_category_accuracy"],
        max_p95_elapsed_seconds=float(max_p95) if max_p95 is not None else None,
        min_summary_approval_rate=minimums["min_summary_approval_rate"],
        min_conversation_prompt_approval_rate=minimums[
            "min_conversation_prompt_approval_rate"
        ],
    )


def load_evaluation_plan(path: str) -> VrtAudioEvaluationPlan:
    """Load bounded cases and aggregate criteria without exposing audio paths."""

    manifest_path = Path(path).expanduser().resolve()
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise VrtPipelineVerificationError("評価用マニフェストを読み取れませんでした。") from error
    if (
        not isinstance(payload, dict)
        or not set(payload) <= {"cases", "acceptance"}
        or "cases" not in payload
        or not isinstance(payload["cases"], list)
    ):
        raise VrtPipelineVerificationError(
            "評価用マニフェストはcases配列と任意のacceptanceだけを含むJSONにしてください。"
        )
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
    optional_fields = {"expected_category"}
    for item in payload["cases"]:
        if (
            not isinstance(item, dict)
            or not required_fields <= set(item)
            or not set(item) <= required_fields | optional_fields
        ):
            raise VrtPipelineVerificationError("各評価ケースの項目が正しくありません。")
        case_id = item["case_id"]
        audio_path = item["audio_path"]
        expected_speaker_count = item["expected_speaker_count"]
        expected_candidate = item["expected_candidate"]
        raw_expected_category = item.get("expected_category")
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
        try:
            expected_category = (
                RecordCategory(raw_expected_category)
                if raw_expected_category is not None
                else None
            )
        except ValueError as error:
            raise VrtPipelineVerificationError(
                "expected_categoryはgrowth、injury、nullのいずれかにしてください。"
            ) from error
        if not expected_candidate and expected_category is not None:
            raise VrtPipelineVerificationError(
                "expected_candidate=falseのケースではexpected_categoryをnullにしてください。"
            )
        seen_ids.add(case_id)
        cases.append(
            VrtAudioEvaluationCase(
                case_id=case_id,
                audio_path=(manifest_path.parent / audio_path).resolve(),
                expected_speaker_count=expected_speaker_count,
                expected_candidate=expected_candidate,
                expected_category=expected_category,
            )
        )
    acceptance = _load_acceptance(payload.get("acceptance"))
    if acceptance.min_category_accuracy is not None and not any(
        case.expected_category is not None for case in cases
    ):
        raise VrtPipelineVerificationError(
            "分類精度の合格基準を使う場合はexpected_categoryを1件以上設定してください。"
        )
    return VrtAudioEvaluationPlan(cases=cases, acceptance=acceptance)


def load_evaluation_manifest(path: str) -> list[VrtAudioEvaluationCase]:
    """Backward-compatible case loader used by existing callers."""

    return load_evaluation_plan(path).cases


def evaluate_audio_cases(
    *,
    verifier: EvaluationVerifier,
    cases: list[VrtAudioEvaluationCase],
    max_file_bytes: int,
    timeout_seconds: float,
    poll_seconds: float,
    monotonic: Callable[[], float] = time.monotonic,
    on_case_start: Callable[[int, int, str], None] | None = None,
    review_candidate: Callable[[str, RecordCategory | None], VrtAudioHumanReview]
    | None = None,
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
                    expected_category=case.expected_category,
                    candidate_category=None,
                    used_low_volume_retry=None,
                    elapsed_seconds=monotonic() - started_at,
                    processing_completed=False,
                    speaker_count_matches=False,
                    candidate_matches=False,
                    category_matches=(False if case.expected_category is not None else None),
                )
            )
            continue

        processing_completed = completed.status == CloudAudioJobStatus.completed
        elapsed_seconds = monotonic() - started_at
        candidate_created = completed.created_candidate if processing_completed else None
        category_matches = (
            completed.candidate_category == case.expected_category
            if case.expected_category is not None
            else None
        )
        human_review = None
        if candidate_created and review_candidate is not None:
            human_review = review_candidate(case.case_id, completed.candidate_category)
        results.append(
            VrtAudioEvaluationResult(
                case_id=case.case_id,
                status=completed.status.value,
                expected_speaker_count=case.expected_speaker_count,
                detected_speaker_count=completed.detected_speaker_count,
                expected_candidate=case.expected_candidate,
                candidate_created=candidate_created,
                expected_category=case.expected_category,
                candidate_category=completed.candidate_category,
                used_low_volume_retry=completed.used_low_volume_retry,
                elapsed_seconds=elapsed_seconds,
                processing_completed=processing_completed,
                speaker_count_matches=(
                    completed.detected_speaker_count == case.expected_speaker_count
                ),
                candidate_matches=(candidate_created == case.expected_candidate),
                category_matches=category_matches,
                summary_acceptable=(
                    human_review.summary_acceptable if human_review is not None else None
                ),
                conversation_prompt_acceptable=(
                    human_review.conversation_prompt_acceptable
                    if human_review is not None
                    else None
                ),
            )
        )
    return results


def _rate(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 3) if denominator else None


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return round(ordered[lower], 3)
    interpolated = ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)
    return round(interpolated, 3)


def _criteria_dict(criteria: VrtAudioAcceptanceCriteria) -> dict[str, object]:
    return {
        "min_processing_completion_rate": criteria.min_processing_completion_rate,
        "min_speaker_count_accuracy": criteria.min_speaker_count_accuracy,
        "min_candidate_accuracy": criteria.min_candidate_accuracy,
        "min_category_accuracy": criteria.min_category_accuracy,
        "max_p95_elapsed_seconds": criteria.max_p95_elapsed_seconds,
        "min_summary_approval_rate": criteria.min_summary_approval_rate,
        "min_conversation_prompt_approval_rate": (
            criteria.min_conversation_prompt_approval_rate
        ),
    }


def build_evaluation_report(
    results: list[VrtAudioEvaluationResult],
    acceptance: VrtAudioAcceptanceCriteria | None = None,
) -> dict[str, object]:
    """Build a report that contains no paths, transcripts, names, or job IDs."""

    criteria = acceptance or VrtAudioAcceptanceCriteria()
    total = len(results)
    passed = sum(result.passed for result in results)
    speaker_matches = sum(result.speaker_count_matches for result in results)
    candidate_matches = sum(result.candidate_matches for result in results)
    expected_candidates = sum(result.expected_candidate for result in results)
    actual_candidates = sum(result.candidate_created is True for result in results)
    true_positives = sum(
        result.expected_candidate and result.candidate_created is True for result in results
    )
    true_negatives = sum(
        not result.expected_candidate and result.candidate_created is False for result in results
    )
    false_positives = sum(
        not result.expected_candidate and result.candidate_created is True for result in results
    )
    false_negatives = sum(
        result.expected_candidate and result.candidate_created is False for result in results
    )
    category_results = [
        result for result in results if result.expected_category is not None
    ]
    category_accuracy = _rate(
        sum(result.category_matches is True for result in category_results),
        len(category_results),
    )
    completed_latencies = [
        result.elapsed_seconds for result in results if result.processing_completed
    ]
    reviewed_results = [
        result
        for result in results
        if result.summary_acceptable is not None
        and result.conversation_prompt_acceptable is not None
    ]
    processing_completion_rate = _rate(
        sum(result.processing_completed for result in results), total
    ) or 0.0
    speaker_accuracy = _rate(speaker_matches, total) or 0.0
    candidate_accuracy = _rate(candidate_matches, total) or 0.0
    review_coverage = _rate(len(reviewed_results), actual_candidates)
    summary_approval_rate = _rate(
        sum(result.summary_acceptable is True for result in reviewed_results),
        len(reviewed_results),
    )
    prompt_approval_rate = _rate(
        sum(result.conversation_prompt_acceptable is True for result in reviewed_results),
        len(reviewed_results),
    )
    p95_elapsed = _percentile(completed_latencies, 0.95)
    checks: dict[str, bool] = {
        "processing_completion_rate": (
            processing_completion_rate >= criteria.min_processing_completion_rate
        ),
        "speaker_count_accuracy": speaker_accuracy >= criteria.min_speaker_count_accuracy,
        "candidate_accuracy": candidate_accuracy >= criteria.min_candidate_accuracy,
    }
    if criteria.min_category_accuracy is not None:
        checks["category_accuracy"] = (
            category_accuracy is not None
            and category_accuracy >= criteria.min_category_accuracy
        )
    if criteria.max_p95_elapsed_seconds is not None:
        checks["p95_elapsed_seconds"] = (
            p95_elapsed is not None and p95_elapsed <= criteria.max_p95_elapsed_seconds
        )
    if (
        criteria.min_summary_approval_rate is not None
        or criteria.min_conversation_prompt_approval_rate is not None
    ):
        checks["human_review_coverage"] = (
            actual_candidates > 0 and review_coverage == 1.0
        )
    if criteria.min_summary_approval_rate is not None:
        checks["summary_approval_rate"] = (
            summary_approval_rate is not None
            and summary_approval_rate >= criteria.min_summary_approval_rate
        )
    if criteria.min_conversation_prompt_approval_rate is not None:
        checks["conversation_prompt_approval_rate"] = (
            prompt_approval_rate is not None
            and prompt_approval_rate >= criteria.min_conversation_prompt_approval_rate
        )
    overall_passed = all(checks.values())
    return {
        "schema_version": 2,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total": total,
            "passed": passed,
            "failed": total - passed,
            "processing_completed": sum(result.processing_completed for result in results),
            "processing_completion_rate": processing_completion_rate,
            "speaker_count_accuracy": speaker_accuracy,
            "candidate_accuracy": candidate_accuracy,
            "expected_candidates": expected_candidates,
            "actual_candidates": actual_candidates,
            "candidate_confusion": {
                "true_positive": true_positives,
                "true_negative": true_negatives,
                "false_positive": false_positives,
                "false_negative": false_negatives,
                "not_evaluated": sum(result.candidate_created is None for result in results),
            },
            "category_evaluated": len(category_results),
            "category_accuracy": category_accuracy,
            "elapsed_seconds": {
                "p50": _percentile(completed_latencies, 0.5),
                "p95": p95_elapsed,
                "max": round(max(completed_latencies), 3) if completed_latencies else None,
            },
            "human_review": {
                "required": (
                    criteria.min_summary_approval_rate is not None
                    or criteria.min_conversation_prompt_approval_rate is not None
                ),
                "reviewed": len(reviewed_results),
                "coverage": review_coverage,
                "summary_approval_rate": summary_approval_rate,
                "conversation_prompt_approval_rate": prompt_approval_rate,
            },
            "overall_passed": overall_passed,
        },
        "acceptance": {
            "criteria": _criteria_dict(criteria),
            "checks": checks,
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
