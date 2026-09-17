"""Same-school, opt-in speaker suggestions; never change record ownership."""

from datetime import datetime
from collections.abc import Iterator
from pathlib import Path
from typing import Protocol

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models import Teacher, TeacherVoiceprint, VoiceEnrollmentConsent, utc_now
from app.voiceprint import cosine_similarity, decrypt_embedding
from app.speaker_diarization import SpeakerDiarizationResult


class SpeakerEmbeddingExtractor(Protocol):
    model_name: str

    def extract_waveform(self, waveform: object, sample_rate: int) -> list[float]: ...


def _eligible_query(
    school_id: str, model_name: str, *, before: datetime | None = None,
) -> Select:
    now = utc_now()
    query = select(TeacherVoiceprint).join(Teacher, Teacher.id == TeacherVoiceprint.teacher_id).join(
        VoiceEnrollmentConsent, VoiceEnrollmentConsent.teacher_id == Teacher.id,
    ).where(
        Teacher.school_id == school_id, Teacher.is_active.is_(True),
        TeacherVoiceprint.school_id == school_id, TeacherVoiceprint.model_name == model_name,
        TeacherVoiceprint.expires_at > now,
        VoiceEnrollmentConsent.school_id == school_id,
        VoiceEnrollmentConsent.purpose == "teacher_voiceprint_enrollment",
        VoiceEnrollmentConsent.allows_recorder_identification.is_(True),
        VoiceEnrollmentConsent.revoked_at.is_(None), VoiceEnrollmentConsent.expires_at > now,
    )
    if before is not None:
        query = query.where(
            VoiceEnrollmentConsent.consented_at <= before, TeacherVoiceprint.enrolled_at <= before,
        )
    return query


def eligible_voiceprints(
    db: Session, school_id: str, model_name: str, *, before: datetime | None = None,
) -> list[TeacherVoiceprint]:
    return list(db.scalars(_eligible_query(school_id, model_name, before=before)))


def eligible_teacher_ids(
    db: Session, school_id: str, model_name: str, *, before: datetime | None = None,
) -> set[str]:
    query = _eligible_query(school_id, model_name, before=before)
    return set(db.scalars(query.with_only_columns(TeacherVoiceprint.teacher_id)))


def choose_match(
    embedding: list[float], references: list[tuple[str, list[float]]], *, threshold: float, margin: float,
) -> str | None:
    scores = sorted(
        ((cosine_similarity(embedding, vector), teacher_id) for teacher_id, vector in references),
        reverse=True,
    )
    if not scores or scores[0][0] < threshold:
        return None
    if len(scores) > 1 and scores[0][0] - scores[1][0] < margin:
        return None
    return scores[0][1]


def clean_intervals(diarization: SpeakerDiarizationResult, label: str) -> Iterator[tuple[float, float]]:
    """Subtract known overlap, including overlap hidden by exclusive diarization."""
    blocked = list(diarization.overlap_intervals)
    blocked.extend((s.start_seconds, s.end_seconds) for s in diarization.segments if s.speaker_label != label)
    clean = []
    for segment in diarization.segments:
        if segment.speaker_label != label:
            continue
        remaining = [(segment.start_seconds, segment.end_seconds)]
        for start, end in blocked:
            parts = []
            for a, b in remaining:
                if end <= a or start >= b:
                    parts.append((a, b))
                else:
                    if a < start:
                        parts.append((a, start))
                    if end < b:
                        parts.append((end, b))
            remaining = parts
        clean.extend(remaining)
    merged: list[tuple[float, float]] = []
    for start, end in sorted(clean):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    yield from merged


class RecorderVoiceprintMatcher:
    def __init__(self, *, db: Session, school_id: str, extractor: SpeakerEmbeddingExtractor, encryption_key: str,
                 threshold: float, margin: float) -> None:
        self.db = db
        self.school_id = school_id
        self.extractor = extractor
        self.encryption_key = encryption_key
        self.threshold = threshold
        self.margin = margin
        self.started_at = utc_now()
        self.matches: set[str] = set()
        self.failed = False

    def observe(self, path: Path, diarization: SpeakerDiarizationResult | None) -> None:
        references = []
        snapshots = []
        waveform = excerpt = embedding = None
        pieces = []
        try:
            # Do not hold a transaction open during model inference.
            snapshots = [(v.teacher_id, v.encrypted_embedding) for v in eligible_voiceprints(
                self.db, self.school_id, self.extractor.model_name, before=self.started_at,
            )]
            self.db.commit()
            if not snapshots or diarization is None:
                return
            for teacher, value in snapshots:
                references.append((teacher, decrypt_embedding(value, self.encryption_key)))
            snapshots.clear()
            import torch
            from pyannote.audio.core.io import Audio

            waveform, rate = Audio(sample_rate=16000, mono="downmix")(str(path))
            labels = sorted({s.speaker_label for s in diarization.segments})
            # Excessively fragmented/noisy recordings are not identity evidence.
            if len(labels) > 8:
                self.failed = True
                self.matches.clear()
                return
            for label in labels:
                pieces.clear()
                count = 0
                for start, end in clean_intervals(diarization, label):
                    a, b = max(0, int(start * rate)), min(waveform.shape[-1], int(end * rate))
                    length = min(max(0, b - a), 10 * rate - count)
                    if length:
                        pieces.append(waveform[:, a:a + length])
                        count += length
                    if count == 10 * rate:
                        break
                if count < 3 * rate:
                    continue
                excerpt = torch.cat(pieces, dim=-1)
                if (not torch.isfinite(excerpt).all() or excerpt.square().mean().sqrt() < 0.005
                        or (excerpt.abs() >= 0.99).float().mean() > 0.01):
                    excerpt.zero_()
                    excerpt = None
                    continue
                embedding = self.extractor.extract_waveform(excerpt, rate)
                match = choose_match(embedding, references, threshold=self.threshold, margin=self.margin)
                if match is None and any(
                    cosine_similarity(embedding, vector) >= self.threshold for _, vector in references
                ):
                    self.failed = True
                    self.matches.clear()
                    return
                embedding.clear()
                if match is not None:
                    self.matches.add(match)
                excerpt.zero_()
                excerpt = None
        except Exception:
            # Identity inference failure must not discard an otherwise usable record.
            self.failed = True
            self.matches.clear()
            self.db.rollback()
            print("録音の声紋照合: 先生未特定（照合を完了できませんでした）", flush=True)
        finally:
            if embedding is not None:
                embedding.clear()
            for _, vector in references:
                vector.clear()
            if excerpt is not None:
                excerpt.zero_()
            if waveform is not None:
                waveform.zero_()
            pieces.clear()
            snapshots.clear()

    def candidate(self) -> str | None:
        if self.failed or len(self.matches) != 1:
            return None
        teacher_id = next(iter(self.matches))
        eligible = eligible_teacher_ids(
            self.db, self.school_id, self.extractor.model_name, before=self.started_at,
        )
        return teacher_id if teacher_id in eligible else None
