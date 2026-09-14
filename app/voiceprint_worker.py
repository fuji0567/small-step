"""GPU-worker helpers for short-lived voiceprint enrollment and verification jobs."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.cloud_audio import CloudAudioJobStorage
from app.models import (
    Teacher,
    TeacherVoiceprint,
    VoiceEnrollmentConsent,
    VoiceprintJob,
    VoiceprintJobKind,
    VoiceprintJobStatus,
    utc_now,
)
from app.voiceprint import (
    VoiceprintError,
    VoiceprintExtractor,
    cosine_similarity,
    decrypt_embedding,
    encrypt_embedding,
)


DEFAULT_PROCESSING_TIMEOUT = timedelta(minutes=10)


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def _active_consent(db: Session, teacher_id: str, now: datetime) -> VoiceEnrollmentConsent:
    consent = db.scalar(
        select(VoiceEnrollmentConsent).where(VoiceEnrollmentConsent.teacher_id == teacher_id)
    )
    if consent is None or consent.revoked_at is not None or _as_utc(consent.expires_at) <= now:
        raise VoiceprintError("Active voiceprint consent is required")
    return consent


def expire_voiceprint_jobs(
    *, db: Session, storage: CloudAudioJobStorage, now: datetime | None = None
) -> int:
    current_time = now or utc_now()
    terminal_jobs = list(
        db.scalars(
            select(VoiceprintJob).where(
                VoiceprintJob.status.in_(
                    [
                        VoiceprintJobStatus.completed,
                        VoiceprintJobStatus.failed,
                        VoiceprintJobStatus.expired,
                    ]
                ),
                VoiceprintJob.expires_at <= current_time,
            )
        )
    )
    for job in terminal_jobs:
        storage.delete(job.storage_key)
        db.delete(job)

    jobs = list(
        db.scalars(
            select(VoiceprintJob).where(
                VoiceprintJob.status == VoiceprintJobStatus.queued,
                VoiceprintJob.expires_at <= current_time,
            )
        )
    )
    for job in jobs:
        job.status = VoiceprintJobStatus.expired
        job.completed_at = current_time
        storage.delete(job.storage_key)
    if jobs or terminal_jobs:
        db.commit()
    return len(jobs)


def delete_expired_voiceprints(
    *, db: Session, storage: CloudAudioJobStorage, now: datetime | None = None
) -> int:
    """Delete expired biometric templates and every related short-lived job."""

    current_time = now or utc_now()
    voiceprints = list(
        db.scalars(
            select(TeacherVoiceprint).where(TeacherVoiceprint.expires_at <= current_time)
        )
    )
    if not voiceprints:
        return 0
    for voiceprint in voiceprints:
        jobs = list(
            db.scalars(
                select(VoiceprintJob).where(
                    VoiceprintJob.teacher_id == voiceprint.teacher_id,
                    VoiceprintJob.created_at <= voiceprint.expires_at,
                )
            )
        )
        for job in jobs:
            storage.delete(job.storage_key)
        db.execute(
            delete(VoiceprintJob).where(
                VoiceprintJob.teacher_id == voiceprint.teacher_id,
                VoiceprintJob.created_at <= voiceprint.expires_at,
            )
        )
        db.delete(voiceprint)
    db.commit()
    return len(voiceprints)


def claim_next_voiceprint_job(
    *,
    db: Session,
    now: datetime | None = None,
    processing_timeout: timedelta = DEFAULT_PROCESSING_TIMEOUT,
) -> VoiceprintJob | None:
    current_time = now or utc_now()
    if processing_timeout <= timedelta():
        raise ValueError("processing_timeout must be positive")
    stale_before = current_time - processing_timeout
    claimable = (
        (VoiceprintJob.status == VoiceprintJobStatus.queued)
        & (VoiceprintJob.expires_at > current_time)
    ) | (
        (VoiceprintJob.status == VoiceprintJobStatus.processing)
        & (
            VoiceprintJob.processing_started_at.is_(None)
            | (VoiceprintJob.processing_started_at <= stale_before)
        )
    )
    candidate_id = (
        select(VoiceprintJob.id)
        .where(claimable)
        .order_by(VoiceprintJob.queued_at)
        .limit(1)
        .scalar_subquery()
    )
    claim_token = str(uuid4())
    job_id = db.scalar(
        update(VoiceprintJob)
        .where(VoiceprintJob.id == candidate_id, claimable)
        .values(
            status=VoiceprintJobStatus.processing,
            attempts=VoiceprintJob.attempts + 1,
            claim_token=claim_token,
            processing_started_at=current_time,
        )
        .returning(VoiceprintJob.id)
    )
    if job_id is None:
        db.rollback()
        return None
    db.commit()
    return db.get(VoiceprintJob, job_id)


def process_next_voiceprint_job(
    *,
    db: Session,
    storage: CloudAudioJobStorage,
    extractor: VoiceprintExtractor,
    encryption_key: str,
    match_threshold: float,
    now: datetime | None = None,
    processing_timeout: timedelta = DEFAULT_PROCESSING_TIMEOUT,
) -> VoiceprintJob | None:
    """Complete one enrollment or verification job and always remove its raw audio."""

    current_time = now or utc_now()
    delete_expired_voiceprints(db=db, storage=storage, now=current_time)
    expire_voiceprint_jobs(db=db, storage=storage, now=current_time)
    job = claim_next_voiceprint_job(
        db=db, now=current_time, processing_timeout=processing_timeout
    )
    if job is None:
        return None
    claim_token = job.claim_token
    if claim_token is None:
        raise RuntimeError("A claimed voiceprint job must have a claim token")

    owns_finalization = False
    try:
        teacher = db.get(Teacher, job.teacher_id)
        if teacher is None or not teacher.is_active or teacher.school_id != job.school_id:
            raise VoiceprintError("Teacher is unavailable")
        consent = _active_consent(db, job.teacher_id, current_time)
        embedding = extractor.extract(str(storage.path_for(job.storage_key)))

        similarity_score = None
        matched = None
        if job.kind == VoiceprintJobKind.enrollment:
            voiceprint = db.scalar(
                select(TeacherVoiceprint).where(TeacherVoiceprint.teacher_id == job.teacher_id)
            )
            if voiceprint is None:
                voiceprint = TeacherVoiceprint(
                    school_id=job.school_id,
                    teacher_id=job.teacher_id,
                    encrypted_embedding="",
                    embedding_dimension=len(embedding),
                    model_name=extractor.model_name,
                    expires_at=consent.expires_at,
                )
                db.add(voiceprint)
            voiceprint.encrypted_embedding = encrypt_embedding(embedding, encryption_key)
            voiceprint.embedding_dimension = len(embedding)
            voiceprint.model_name = extractor.model_name
            voiceprint.enrolled_at = current_time
            voiceprint.expires_at = consent.expires_at
        else:
            voiceprint = db.scalar(
                select(TeacherVoiceprint).where(TeacherVoiceprint.teacher_id == job.teacher_id)
            )
            if voiceprint is None or _as_utc(voiceprint.expires_at) <= current_time:
                raise VoiceprintError("An active enrolled voiceprint is required")
            if voiceprint.model_name != extractor.model_name:
                raise VoiceprintError("Voiceprint model changed; enrollment must be renewed")
            enrolled = decrypt_embedding(voiceprint.encrypted_embedding, encryption_key)
            if len(enrolled) != voiceprint.embedding_dimension:
                raise VoiceprintError("Stored voiceprint dimension is invalid")
            similarity_score = round(cosine_similarity(enrolled, embedding), 6)
            matched = similarity_score >= match_threshold

        completed = db.execute(
            update(VoiceprintJob)
            .where(
                VoiceprintJob.id == job.id,
                VoiceprintJob.status == VoiceprintJobStatus.processing,
                VoiceprintJob.claim_token == claim_token,
            )
            .values(
                status=VoiceprintJobStatus.completed,
                similarity_score=similarity_score,
                matched=matched,
                claim_token=None,
                completed_at=utc_now(),
            )
        )
        if completed.rowcount != 1:
            db.rollback()
            return None
        db.commit()
        owns_finalization = True
        return db.get(VoiceprintJob, job.id)
    except Exception:
        db.rollback()
        failed = db.execute(
            update(VoiceprintJob)
            .where(
                VoiceprintJob.id == job.id,
                VoiceprintJob.status == VoiceprintJobStatus.processing,
                VoiceprintJob.claim_token == claim_token,
            )
            .values(
                status=VoiceprintJobStatus.failed,
                claim_token=None,
                completed_at=utc_now(),
            )
        )
        if failed.rowcount == 1:
            db.commit()
            owns_finalization = True
            return db.get(VoiceprintJob, job.id)
        db.rollback()
        return None
    finally:
        if owns_finalization:
            storage.delete(job.storage_key)
