"""GPU-worker helpers for consuming short-lived cloud audio jobs."""

from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
import unicodedata
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.cloud_audio import CloudAudioJobStorage
from app.edge_audio import EdgeAudioCandidate, EdgeAudioError, EdgeAudioProcessor
from app.models import (
    Child,
    CloudAudioJob,
    CloudAudioJobStatus,
    EdgeDevice,
    Record,
    RecordStatus,
    Teacher,
    utc_now,
)


DEFAULT_PROCESSING_TIMEOUT = timedelta(minutes=10)
MAX_PRIOR_RECORDS = 5
MAX_PRIOR_SUMMARY_CHARS = 500
DUPLICATE_WINDOW = timedelta(minutes=2)
DUPLICATE_SIMILARITY_THRESHOLD = 0.9


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def expire_cloud_audio_jobs(*, db: Session, storage: CloudAudioJobStorage, now: datetime | None = None) -> int:
    """Delete queued uploads whose short retention period has elapsed."""

    current_time = now or utc_now()
    jobs = list(
        db.scalars(
            select(CloudAudioJob).where(
                CloudAudioJob.status == CloudAudioJobStatus.queued,
                CloudAudioJob.expires_at <= current_time,
            )
        )
    )
    for job in jobs:
        job.status = CloudAudioJobStatus.expired
        storage.delete(job.storage_key)
    if jobs:
        db.commit()
    return len(jobs)


def claim_next_cloud_audio_job(
    *,
    db: Session,
    now: datetime | None = None,
    processing_timeout: timedelta = DEFAULT_PROCESSING_TIMEOUT,
) -> CloudAudioJob | None:
    """Atomically claim one job, reclaiming only an expired worker lease."""

    current_time = now or utc_now()
    if processing_timeout <= timedelta():
        raise ValueError("processing_timeout must be positive")
    stale_before = current_time - processing_timeout
    claimable = (
        (CloudAudioJob.status == CloudAudioJobStatus.queued)
        & (CloudAudioJob.expires_at > current_time)
    ) | (
        (CloudAudioJob.status == CloudAudioJobStatus.processing)
        & (
            CloudAudioJob.processing_started_at.is_(None)
            | (CloudAudioJob.processing_started_at <= stale_before)
        )
    )
    candidate_id = (
        select(CloudAudioJob.id)
        .where(claimable)
        .order_by(CloudAudioJob.queued_at)
        .limit(1)
        .scalar_subquery()
    )
    claim_token = str(uuid4())
    job_id = db.scalar(
        update(CloudAudioJob)
        .where(
            CloudAudioJob.id == candidate_id,
            claimable,
        )
        .values(
            status=CloudAudioJobStatus.processing,
            attempts=CloudAudioJob.attempts + 1,
            claim_token=claim_token,
            processing_started_at=current_time,
        )
        .returning(CloudAudioJob.id)
    )
    if job_id is None:
        db.rollback()
        return None
    db.commit()
    return db.get(CloudAudioJob, job_id)


def _create_record_from_cloud_job(
    *,
    db: Session,
    job: CloudAudioJob,
    candidate: EdgeAudioCandidate,
) -> Record:
    if not candidate.recordable or candidate.category is None or candidate.summary is None:
        raise EdgeAudioError("Audio without a concrete event cannot create a record")
    device = db.get(EdgeDevice, job.device_id)
    if device is None or not device.is_active:
        raise EdgeAudioError("The source edge device is no longer active")
    teacher = db.get(Teacher, job.teacher_id)
    if teacher is None or not teacher.is_active:
        raise EdgeAudioError("The source teacher is no longer active")
    if job.child_id:
        child = db.get(Child, job.child_id)
        if child is None or child.school_id != job.school_id or not child.is_active:
            raise EdgeAudioError("The selected child is no longer available")
    return Record(
        school_id=job.school_id,
        teacher_id=job.teacher_id,
        child_id=job.child_id,
        category=candidate.category,
        source_event_id=f"cloud-audio-job-{job.id}",
        confidence=candidate.confidence,
        occurred_at=_as_utc(job.queued_at),
        summary=candidate.summary,
        conversation_prompt=candidate.conversation_prompt,
        anonymized_context=candidate.anonymized_context,
    )


def _recent_approved_context(*, db: Session, job: CloudAudioJob) -> str | None:
    """Build bounded, anonymous context from the same child's reviewed history."""

    if not job.child_id:
        return None
    records = list(
        db.scalars(
            select(Record)
            .where(
                Record.child_id == job.child_id,
                Record.school_id == job.school_id,
                Record.status.in_((RecordStatus.approved, RecordStatus.dispatched)),
                Record.occurred_at < job.queued_at,
            )
            .order_by(Record.occurred_at.desc())
            .limit(MAX_PRIOR_RECORDS)
        )
    )
    if not records:
        return None

    current_date = _as_utc(job.queued_at).date()
    lines: list[str] = []
    for record in records:
        record_date = _as_utc(record.occurred_at).date()
        days_ago = (current_date - record_date).days
        timing = "前日" if days_ago == 1 else record_date.isoformat()
        category = "けが" if record.category.value == "injury" else "成長"
        summary = record.summary[:MAX_PRIOR_SUMMARY_CHARS]
        lines.append(f"{timing}・{category}: {summary}")
    return "\n".join(lines)


def _normalized_summary(value: str) -> str:
    return "".join(
        character
        for character in unicodedata.normalize("NFKC", value).casefold()
        if character.isalnum()
    )


def _find_recent_duplicate_record(
    *,
    db: Session,
    job: CloudAudioJob,
    candidate: EdgeAudioCandidate,
) -> Record | None:
    """Reuse a near-identical pending record from an adjacent audio chunk."""

    if (
        not job.child_id
        or not candidate.recordable
        or candidate.category is None
        or candidate.summary is None
    ):
        return None
    normalized_candidate = _normalized_summary(candidate.summary)
    if not normalized_candidate:
        return None

    recent_records = db.scalars(
        select(Record)
        .join(CloudAudioJob, CloudAudioJob.record_id == Record.id)
        .where(
            CloudAudioJob.device_id == job.device_id,
            CloudAudioJob.status == CloudAudioJobStatus.completed,
            CloudAudioJob.queued_at >= job.queued_at - DUPLICATE_WINDOW,
            CloudAudioJob.queued_at < job.queued_at,
            Record.school_id == job.school_id,
            Record.child_id == job.child_id,
            Record.category == candidate.category,
            Record.status == RecordStatus.pending_review,
        )
        .order_by(CloudAudioJob.queued_at.desc())
        .limit(3)
    )
    for record in recent_records:
        normalized_existing = _normalized_summary(record.summary)
        if not normalized_existing:
            continue
        similarity = SequenceMatcher(
            None,
            normalized_candidate,
            normalized_existing,
            autojunk=False,
        ).ratio()
        if similarity >= DUPLICATE_SIMILARITY_THRESHOLD:
            return record
    return None


def process_next_cloud_audio_job(
    *,
    db: Session,
    storage: CloudAudioJobStorage,
    processor: EdgeAudioProcessor,
    now: datetime | None = None,
    processing_timeout: timedelta = DEFAULT_PROCESSING_TIMEOUT,
) -> CloudAudioJob | None:
    """Analyze one job, create a pending-review record, then delete raw audio."""

    current_time = now or utc_now()
    expire_cloud_audio_jobs(db=db, storage=storage, now=current_time)
    job = claim_next_cloud_audio_job(
        db=db,
        now=current_time,
        processing_timeout=processing_timeout,
    )
    if job is None:
        return None
    claim_token = job.claim_token
    if claim_token is None:
        raise RuntimeError("A claimed cloud audio job must have a claim token")

    owns_finalization = False
    try:
        audio_path = storage.path_for(job.storage_key)
        candidate = processor.analyze_trusted_cloud_audio_file(
            str(audio_path),
            prior_context=_recent_approved_context(db=db, job=job),
        )
        record = None
        record_id = None
        if candidate.recordable:
            record = _create_record_from_cloud_job(db=db, job=job, candidate=candidate)
            duplicate = _find_recent_duplicate_record(db=db, job=job, candidate=candidate)
            if duplicate is not None:
                record_id = duplicate.id
            else:
                db.add(record)
                db.flush()
                record_id = record.id
        completed = db.execute(
            update(CloudAudioJob)
            .where(
                CloudAudioJob.id == job.id,
                CloudAudioJob.status == CloudAudioJobStatus.processing,
                CloudAudioJob.claim_token == claim_token,
            )
            .values(
                status=CloudAudioJobStatus.completed,
                record_id=record_id,
                claim_token=None,
                completed_at=utc_now(),
            )
        )
        if completed.rowcount != 1:
            # A newer worker reclaimed this job. Roll back this worker's record
            # so only the current lease owner can create a result.
            db.rollback()
            return None
        db.commit()
        owns_finalization = True
        return db.get(CloudAudioJob, job.id)
    except Exception:
        # Model, codec, and database failures must never leave a raw upload behind.
        db.rollback()
        failed = db.execute(
            update(CloudAudioJob)
            .where(
                CloudAudioJob.id == job.id,
                CloudAudioJob.status == CloudAudioJobStatus.processing,
                CloudAudioJob.claim_token == claim_token,
            )
            .values(
                status=CloudAudioJobStatus.failed,
                claim_token=None,
                completed_at=utc_now(),
            )
        )
        if failed.rowcount == 1:
            db.commit()
            owns_finalization = True
            return db.get(CloudAudioJob, job.id)
        db.rollback()
        return None
    finally:
        # Only the current lease owner may remove the raw upload. A stale worker
        # must leave it available for the worker that safely reclaimed the job.
        if owns_finalization:
            storage.delete(job.storage_key)
