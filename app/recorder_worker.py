"""Consume recorder sessions without persisting transcripts or intermediate summaries."""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Event, Thread
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.edge_audio import EdgeAudioCandidate, EdgeAudioError, EdgeAudioProcessor, NoSpeechDetectedError
from app.models import Record, RecordCategory, RecordingSegment, RecordingSession, RecordingSessionStatus, Teacher, utc_now
from app.recorder import RecorderStorage, RecorderStorageError
from app.recorder_voiceprint import RecorderVoiceprintMatcher, SpeakerEmbeddingExtractor
from app.recorder_children import RecorderChildMatcher


DEFAULT_PROCESSING_TIMEOUT = timedelta(minutes=10)
ACTIVE_STATUSES = (
    RecordingSessionStatus.draft, RecordingSessionStatus.queued, RecordingSessionStatus.processing
)
TERMINAL_STATUSES = (
    RecordingSessionStatus.completed, RecordingSessionStatus.failed,
    RecordingSessionStatus.discarded, RecordingSessionStatus.expired,
)


class LostRecorderClaim(RuntimeError):
    """A timed-out worker must not publish its in-memory result."""


@dataclass(frozen=True)
class SegmentInput:
    sequence: int
    storage_key: str
    size_bytes: int
    sha256: str
    duration_ms: int


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def cleanup_recorder_sessions(
    *, db: Session, storage: RecorderStorage, now: datetime | None = None,
    processing_timeout: timedelta = DEFAULT_PROCESSING_TIMEOUT,
    orphan_retention: timedelta = timedelta(hours=24),
) -> int:
    """Expire abandoned work and retry terminal/orphan file cleanup after crashes."""

    if processing_timeout <= timedelta() or orphan_retention <= timedelta():
        raise ValueError("Recorder timeouts must be positive")
    current_time = now or utc_now()
    expired_ids = list(db.scalars(
        update(RecordingSession)
        .where(RecordingSession.status.in_(ACTIVE_STATUSES), RecordingSession.expires_at <= current_time)
        .values(status=RecordingSessionStatus.expired, claim_token=None, updated_at=current_time)
        .returning(RecordingSession.id)
    ))
    # Completed segments have already been deleted. Reclaiming a crashed session
    # would silently lose that context, so fail it instead of replaying the remainder.
    stale_ids = list(db.scalars(
        update(RecordingSession)
        .where(
            RecordingSession.status == RecordingSessionStatus.processing,
            RecordingSession.updated_at <= current_time - processing_timeout,
        )
        .values(status=RecordingSessionStatus.failed, claim_token=None, updated_at=current_time)
        .returning(RecordingSession.id)
    ))
    db.commit()
    if not storage.session_dir.exists():
        return len(expired_ids) + len(stale_ids)

    directories = []
    for directory in storage.session_dir.iterdir():
        try:
            if str(UUID(directory.name)) == directory.name:
                directories.append(directory)
        except ValueError:
            continue
    states = {}
    for offset in range(0, len(directories), 500):
        states.update(db.execute(
            select(RecordingSession.id, RecordingSession.status)
            .where(RecordingSession.id.in_([
                directory.name for directory in directories[offset:offset + 500]
            ]))
        ).all())
    db.commit()
    for directory in directories:
        state = states.get(directory.name)
        try:
            orphan_expired = (
                state is None
                and directory.lstat().st_mtime <= (current_time - orphan_retention).timestamp()
            )
            if state in TERMINAL_STATUSES or orphan_expired:
                storage.delete_session(directory.name)
        except (OSError, RecorderStorageError):
            print("録音音声の後片付けを次回再試行します。")
    return len(expired_ids) + len(stale_ids)


def claim_next_recorder_session(*, db: Session, now: datetime | None = None) -> RecordingSession | None:
    """Atomically claim queued work; never take over another processing session."""

    current_time = now or utc_now()
    claimable = (
        (RecordingSession.status == RecordingSessionStatus.queued)
        & (RecordingSession.expires_at > current_time)
    )
    candidate_id = (
        select(RecordingSession.id).where(claimable)
        .order_by(RecordingSession.created_at, RecordingSession.id).limit(1).scalar_subquery()
    )
    session_id = db.scalar(
        update(RecordingSession)
        .where(RecordingSession.id == candidate_id, claimable)
        .values(
            status=RecordingSessionStatus.processing, claim_token=str(uuid4()),
            updated_at=current_time, processed_segment_count=0, failed_segment_count=0,
        )
        .returning(RecordingSession.id)
    )
    db.commit()
    return db.get(RecordingSession, session_id) if session_id else None


def _renew_claim(
    *, db: Session, session_id: str, claim_token: str, processed: int, failed: int,
) -> None:
    current_time = utc_now()
    renewed = db.execute(
        update(RecordingSession)
        .where(
            RecordingSession.id == session_id,
            RecordingSession.status == RecordingSessionStatus.processing,
            RecordingSession.claim_token == claim_token,
            RecordingSession.expires_at > current_time,
        )
        .values(updated_at=current_time, processed_segment_count=processed, failed_segment_count=failed)
    )
    db.commit()
    if renewed.rowcount != 1:
        raise LostRecorderClaim()


def _validate_owner(db: Session, session: RecordingSession) -> None:
    teacher = db.get(Teacher, session.teacher_id)
    if teacher is None or not teacher.is_active or teacher.school_id != session.school_id:
        raise EdgeAudioError("The recorder owner is no longer available")


def _verified_path(storage: RecorderStorage, session_id: str, segment: SegmentInput) -> Path:
    path = storage.path_for(segment.storage_key)
    if path.parent != storage.session_path(session_id) or not path.is_file():
        raise RecorderStorageError("Recorder segment does not belong to the session")
    size = path.stat().st_size
    if size != segment.size_bytes or size > storage.max_segment_bytes:
        raise RecorderStorageError("Recorder segment size changed")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1_048_576):
            digest.update(chunk)
    if not hmac.compare_digest(digest.hexdigest(), segment.sha256):
        raise RecorderStorageError("Recorder segment checksum changed")
    return path


def _finish_session(
    *, db: Session, session: RecordingSession, claim_token: str,
    candidate: EdgeAudioCandidate | None, processed: int, failed: int,
    voiceprint_matcher: RecorderVoiceprintMatcher | None = None,
    child_matcher: RecorderChildMatcher | None = None,
) -> RecordingSession | None:
    _validate_owner(db, session)
    record_id = None
    if candidate is not None:
        record = Record(
            school_id=session.school_id, teacher_id=session.teacher_id, child_id=None,
            source_event_id=f"recorder-session-{session.id}",
            occurred_at=_as_utc(session.created_at),
            audio_processing_incomplete=failed > 0,
            voiceprint_matching_checked=voiceprint_matcher is not None,
            candidate_child_id=child_matcher.candidate(db) if child_matcher and not failed else None,
            voiceprint_candidate_teacher_id=voiceprint_matcher.candidate() if voiceprint_matcher and not failed else None,
            **candidate.record_payload(),
        )
        db.add(record)
        db.flush()
        record_id = record.id
    current_time = utc_now()
    finalized = db.execute(
        update(RecordingSession)
        .where(
            RecordingSession.id == session.id,
            RecordingSession.status == RecordingSessionStatus.processing,
            RecordingSession.claim_token == claim_token,
            RecordingSession.expires_at > current_time,
        )
        .values(
            status=(RecordingSessionStatus.failed if candidate is None and failed else RecordingSessionStatus.completed),
            claim_token=None, record_id=record_id, updated_at=current_time,
            processed_segment_count=processed, failed_segment_count=failed,
        )
    )
    if finalized.rowcount != 1:
        db.rollback()
        return None
    db.commit()
    return db.get(RecordingSession, session.id)


def _log_processing_failure(stage: str, error: Exception) -> None:
    # Never log exception messages, paths, session IDs, or model inputs.
    allowed_types = {
        "ImportError", "ModuleNotFoundError", "MemoryError", "OutOfMemoryError",
        "RuntimeError", "ValueError", "TypeError", "FileNotFoundError",
        "PermissionError", "OSError", "TimeoutError", "ReadTimeout",
        "ConnectTimeout", "ConnectError", "HTTPStatusError",
        "EdgeAudioError", "SpeakerDiarizationError", "RecorderStorageError",
    }
    causes = []
    diagnostics = []
    known_modules = {
        "sklearn.utils.validation": "numeric_validation",
        "sklearn.decomposition._pca": "pca",
        "pyannote.audio.pipelines.clustering": "speaker_clustering",
        "pyannote.audio.pipelines.speaker_diarization": "speaker_pipeline",
        "pyannote.audio.core.inference": "speaker_inference",
        "pyannote.audio.core.io": "audio_decoder",
        "scipy.cluster.hierarchy": "hierarchical_clustering",
    }
    current = error
    seen = set()
    while current is not None and id(current) not in seen and len(causes) < 5:
        seen.add(id(current))
        name = type(current).__name__
        causes.append(name if name in allowed_types else "OtherError")
        if isinstance(current, ValueError):
            message = str(current).lower()
            if "nan" in message or "infinity" in message or "infinite" in message:
                diagnostics.append("invalid_numeric_values")
            elif "sample" in message or "empty" in message or "minimum" in message:
                diagnostics.append("insufficient_or_invalid_shape")
            else:
                diagnostics.append("value_error_unclassified")
        trace = current.__traceback__
        while trace is not None:
            label = known_modules.get(trace.tb_frame.f_globals.get("__name__", ""))
            if label is not None:
                diagnostics.append(f"{label}:{trace.tb_lineno}")
            trace = trace.tb_next
        current = current.__cause__
    print(f"録音処理の失敗: stage={stage}; types={'/'.join(causes)}", flush=True)
    if diagnostics:
        print(f"録音処理の診断: codes={','.join(diagnostics[-8:])}", flush=True)


def process_next_recorder_session(
    *, db: Session, storage: RecorderStorage, processor: EdgeAudioProcessor,
    now: datetime | None = None, processing_timeout: timedelta = DEFAULT_PROCESSING_TIMEOUT,
    max_duration_minutes: int = 60,
    voiceprint_extractor: SpeakerEmbeddingExtractor | None = None,
) -> RecordingSession | None:
    """Analyze ordered files, keep one bounded anonymous accumulator, then erase audio."""

    cleanup_recorder_sessions(db=db, storage=storage, now=now, processing_timeout=processing_timeout)
    session = claim_next_recorder_session(db=db, now=now)
    if session is None:
        return None
    session_id, claim_token = session.id, session.claim_token
    assert claim_token is not None
    processed = failed = 0
    candidate = None
    voiceprint_matcher = None
    settings = getattr(processor, "settings", None)
    child_matcher = (
        RecorderChildMatcher(db=db, school_id=session.school_id)
        if getattr(settings, "recorder_child_matching_enabled", False) else None
    )
    if (settings is not None and settings.recorder_voiceprint_matching_enabled
            and settings.voiceprint_enabled and voiceprint_extractor is not None):
        voiceprint_matcher = RecorderVoiceprintMatcher(
            db=db, school_id=session.school_id, extractor=voiceprint_extractor,
            encryption_key=settings.voiceprint_encryption_key,
            threshold=settings.recorder_voiceprint_match_threshold,
            margin=settings.recorder_voiceprint_match_margin,
        )
    stage = "validation"
    try:
        _validate_owner(db, session)
        segments = tuple(
            SegmentInput(item.sequence, item.storage_key, item.size_bytes, item.sha256, item.duration_ms)
            for item in db.scalars(
                select(RecordingSegment).where(RecordingSegment.session_id == session_id)
                .order_by(RecordingSegment.sequence).limit(max_duration_minutes * 60 + 1)
            )
        )
        # Release database transactions before slow codec/model/LLM calls.
        db.expunge(session)
        db.commit()
        if (
            not segments or len(segments) > max_duration_minutes * 60
            or [item.sequence for item in segments] != list(range(len(segments)))
            or any(item.duration_ms <= 0 for item in segments)
            or sum(item.duration_ms for item in segments) > max_duration_minutes * 60_000
        ):
            raise RecorderStorageError("Invalid recorder segment sequence or duration")

        for segment in segments:
            following = None
            for _attempt in range(2):
                _renew_claim(db=db, session_id=session_id, claim_token=claim_token, processed=processed, failed=failed)
                try:
                    stage = "storage_verification"
                    path = _verified_path(storage, session_id, segment)
                    stage = "audio_analysis"
                    options = {}
                    if voiceprint_matcher is not None:
                        options["speaker_observer"] = voiceprint_matcher.observe
                    if child_matcher is not None:
                        options["child_matcher"] = child_matcher
                    following = processor.analyze_trusted_recorder_audio_file(str(path), **options)
                    if not isinstance(following, EdgeAudioCandidate):
                        raise EdgeAudioError("Invalid recorder analysis")
                    break
                except NoSpeechDetectedError:
                    following = EdgeAudioCandidate(recordable=False, category=None, confidence=0, summary=None)
                    break
                except Exception as error:
                    _log_processing_failure(stage, error)
                    following = None
            if following is None:
                failed += 1
            elif following.recordable:
                if candidate is None:
                    candidate = following
                else:
                    for _attempt in range(2):
                        _renew_claim(db=db, session_id=session_id, claim_token=claim_token, processed=processed, failed=failed)
                        try:
                            stage = "summary_merge"
                            merged = processor.merge_recorder_candidates(candidate, following)
                            if not isinstance(merged, EdgeAudioCandidate) or not merged.recordable:
                                raise EdgeAudioError("Invalid recorder merge")
                            candidate = merged
                            break
                        except Exception as error:
                            _log_processing_failure(stage, error)
                            if _attempt == 1:
                                if RecordCategory.injury in (candidate.category, following.category):
                                    # Do not publish an injury record that silently
                                    # drops another known event after a failed merge.
                                    raise EdgeAudioError("Injury recorder candidates could not be merged")
                                failed += 1
            processed += 1
            stage = "audio_cleanup"
            # Retain no successful segment for a session-wide replay.
            path = storage.path_for(segment.storage_key)
            if path.parent == storage.session_path(session_id):
                storage.delete(segment.storage_key)
            following = None
            _renew_claim(db=db, session_id=session_id, claim_token=claim_token, processed=processed, failed=failed)
        stage = "record_finalization"
        return _finish_session(
            db=db, session=session, claim_token=claim_token,
            candidate=candidate, processed=processed, failed=failed,
            voiceprint_matcher=voiceprint_matcher,
            child_matcher=child_matcher,
        )
    except LostRecorderClaim:
        db.rollback()
        return None
    except Exception as error:
        _log_processing_failure(stage, error)
        db.rollback()
        changed = db.execute(
            update(RecordingSession)
            .where(
                RecordingSession.id == session_id,
                RecordingSession.status == RecordingSessionStatus.processing,
                RecordingSession.claim_token == claim_token,
            )
            .values(status=RecordingSessionStatus.failed, claim_token=None, updated_at=utc_now())
        )
        db.commit()
        return db.get(RecordingSession, session_id) if changed.rowcount == 1 else None
    finally:
        candidate = None
        if child_matcher is not None:
            child_matcher.clear()
        # Processing sessions are never reclaimed. A timed-out original worker
        # cannot delete files belonging to a newer claimant of the same session.
        try:
            storage.delete_session(session_id)
        except (OSError, RecorderStorageError):
            print("録音音声の後片付けを次回再試行します。")


class RecorderMaintenance:
    """Run expiry independently of potentially blocked inference calls."""

    def __init__(self, *, session_factory, storage: RecorderStorage, interval_seconds: float,
                 processing_timeout: timedelta, orphan_retention: timedelta) -> None:
        if interval_seconds <= 0:
            raise ValueError("Recorder maintenance interval must be positive")
        self.session_factory = session_factory
        self.storage = storage
        self.interval_seconds = interval_seconds
        self.processing_timeout = processing_timeout
        self.orphan_retention = orphan_retention
        self.stop_event = Event()
        self.thread: Thread | None = None

    def _pulse(self) -> None:
        with self.session_factory() as db:
            cleanup_recorder_sessions(
                db=db, storage=self.storage, processing_timeout=self.processing_timeout,
                orphan_retention=self.orphan_retention,
            )

    def _run(self) -> None:
        while not self.stop_event.wait(self.interval_seconds):
            try:
                self._pulse()
            except Exception:
                print("録音音声の定期後片付けを次回再試行します。")

    def __enter__(self) -> "RecorderMaintenance":
        self._pulse()
        self.thread = Thread(target=self._run, name="recorder-cleanup", daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *_exc_info: object) -> None:
        self.stop_event.set()
        if self.thread is not None:
            self.thread.join(timeout=5)
