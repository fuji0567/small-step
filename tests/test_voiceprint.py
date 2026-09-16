from datetime import timedelta
from uuid import uuid4

from cryptography.fernet import Fernet
import pytest
from sqlalchemy import select

from app.cloud_audio import CloudAudioJobStorage
from app.database import (
    create_database_engine,
    create_session_factory,
    initialise_database,
)
from app.models import (
    School,
    Teacher,
    TeacherVoiceprint,
    VoiceEnrollmentConsent,
    VoiceprintJob,
    VoiceprintJobKind,
    VoiceprintQualityIssue,
    VoiceprintJobStatus,
    utc_now,
)
from app.voiceprint import (
    VOICEPRINT_ENROLLMENT_SAMPLE_COUNT,
    average_embeddings,
    cosine_similarity,
    decrypt_embedding,
    encrypt_embedding,
)
from app.voiceprint_quality import VoiceprintSampleQuality
from app.voiceprint_worker import (
    delete_expired_voiceprints,
    expire_voiceprint_jobs,
    process_next_voiceprint_job,
)


class FakeExtractor:
    model_name = "test-speaker-model"

    def __init__(self, embedding: list[float]) -> None:
        self.embedding = embedding
        self.calls = 0

    def extract(self, _audio_path: str) -> list[float]:
        self.calls += 1
        return list(self.embedding)


class FakeQualityAnalyzer:
    def __init__(
        self,
        issue: VoiceprintQualityIssue | None = None,
        *,
        issue_on_call: int = 1,
    ) -> None:
        self.issue = issue
        self.issue_on_call = issue_on_call
        self.calls = 0

    def analyze(self, _audio_path) -> VoiceprintSampleQuality:
        self.calls += 1
        issue = self.issue if self.calls == self.issue_on_call else None
        return VoiceprintSampleQuality(
            issue=issue,
            duration_seconds=12.0,
            speech_seconds=10.0,
            speaker_count=(2 if issue == VoiceprintQualityIssue.multiple_speakers else 1),
            clipping_ratio=0.0,
            speech_dbfs=-20.0,
            signal_to_noise_db=20.0,
        )


def add_job(
    session,
    storage,
    *,
    school_id,
    teacher_id,
    kind,
    suffix=".wav",
    sample_count=None,
):
    now = utc_now()
    job = VoiceprintJob(
        school_id=school_id,
        teacher_id=teacher_id,
        kind=kind,
        storage_key="pending",
        expires_at=now + timedelta(minutes=15),
    )
    session.add(job)
    session.flush()
    storage.ensure_directory()
    if sample_count is None:
        sample_count = VOICEPRINT_ENROLLMENT_SAMPLE_COUNT if kind == VoiceprintJobKind.enrollment else 1
    storage_keys = [
        storage.storage_key_for_upload(job_id=str(uuid4()), filename=f"sample-{index}{suffix}")
        for index in range(1, sample_count + 1)
    ]
    job.storage_key = storage_keys[0]
    job.sample_storage_keys = storage_keys
    for storage_key in storage_keys:
        storage.path_for(storage_key).write_bytes(b"test audio")
    session.commit()
    return job


def job_audio_paths(storage, job):
    return [storage.path_for(storage_key) for storage_key in job.sample_storage_keys]


def test_voiceprint_enrollment_and_verification_delete_raw_audio(tmp_path):
    engine = create_database_engine(f"sqlite:///{tmp_path}/voiceprint.db")
    initialise_database(engine)
    Session = create_session_factory(engine)
    storage = CloudAudioJobStorage(job_dir=str(tmp_path / "jobs"), max_file_bytes=1024)
    encryption_key = Fernet.generate_key().decode("ascii")
    now = utc_now()

    with Session() as db:
        school = School(name="声紋テスト園")
        db.add(school)
        db.flush()
        teacher = Teacher(school_id=school.id, name="声紋先生")
        db.add(teacher)
        db.flush()
        db.add(
            VoiceEnrollmentConsent(
                school_id=school.id,
                teacher_id=teacher.id,
                purpose="teacher_voiceprint_enrollment",
                policy_version="test",
                retention_days=30,
                expires_at=now + timedelta(days=30),
            )
        )
        db.commit()
        enrollment = add_job(
            db,
            storage,
            school_id=school.id,
            teacher_id=teacher.id,
            kind=VoiceprintJobKind.enrollment,
            suffix=".webm",
        )
        enrollment_paths = job_audio_paths(storage, enrollment)

        result = process_next_voiceprint_job(
            db=db,
            storage=storage,
            extractor=FakeExtractor([3.0, 4.0]),
            quality_analyzer=FakeQualityAnalyzer(),
            encryption_key=encryption_key,
            match_threshold=0.75,
        )

        assert result is not None
        assert result.status == VoiceprintJobStatus.completed
        assert all(not path.exists() for path in enrollment_paths)
        voiceprint = db.scalar(select(TeacherVoiceprint))
        assert voiceprint is not None
        assert voiceprint.embedding_dimension == 2
        assert voiceprint.sample_count == VOICEPRINT_ENROLLMENT_SAMPLE_COUNT
        assert decrypt_embedding(voiceprint.encrypted_embedding, encryption_key) == [
            0.6,
            0.8,
        ]

        verification = add_job(
            db,
            storage,
            school_id=school.id,
            teacher_id=teacher.id,
            kind=VoiceprintJobKind.verification,
        )
        verification_path = storage.path_for(verification.storage_key)
        result = process_next_voiceprint_job(
            db=db,
            storage=storage,
            extractor=FakeExtractor([6.0, 8.0]),
            quality_analyzer=FakeQualityAnalyzer(),
            encryption_key=encryption_key,
            match_threshold=0.75,
        )

        assert result is not None
        assert result.status == VoiceprintJobStatus.completed
        assert result.matched is True
        assert result.similarity_score == 1.0
        assert not verification_path.exists()

    engine.dispose()


def test_voiceprint_job_fails_closed_without_consent_and_deletes_audio(tmp_path):
    engine = create_database_engine(f"sqlite:///{tmp_path}/voiceprint.db")
    initialise_database(engine)
    Session = create_session_factory(engine)
    storage = CloudAudioJobStorage(job_dir=str(tmp_path / "jobs"), max_file_bytes=1024)

    with Session() as db:
        school = School(name="同意なし園")
        db.add(school)
        db.flush()
        teacher = Teacher(school_id=school.id, name="未同意先生")
        db.add(teacher)
        db.commit()
        job = add_job(
            db,
            storage,
            school_id=school.id,
            teacher_id=teacher.id,
            kind=VoiceprintJobKind.enrollment,
        )
        audio_paths = job_audio_paths(storage, job)

        result = process_next_voiceprint_job(
            db=db,
            storage=storage,
            extractor=FakeExtractor([1.0, 0.0]),
            quality_analyzer=FakeQualityAnalyzer(),
            encryption_key=Fernet.generate_key().decode("ascii"),
            match_threshold=0.75,
        )

        assert result is not None
        assert result.status == VoiceprintJobStatus.failed
        assert all(not path.exists() for path in audio_paths)
        assert db.scalar(select(TeacherVoiceprint)) is None

    engine.dispose()


def test_expired_voiceprint_deletes_template_jobs_and_audio(tmp_path):
    engine = create_database_engine(f"sqlite:///{tmp_path}/voiceprint.db")
    initialise_database(engine)
    Session = create_session_factory(engine)
    storage = CloudAudioJobStorage(job_dir=str(tmp_path / "jobs"), max_file_bytes=1024)
    now = utc_now()

    with Session() as db:
        school = School(name="期限切れ園")
        db.add(school)
        db.flush()
        teacher = Teacher(school_id=school.id, name="期限切れ先生")
        db.add(teacher)
        db.flush()
        db.add(
            TeacherVoiceprint(
                school_id=school.id,
                teacher_id=teacher.id,
                encrypted_embedding="encrypted",
                embedding_dimension=2,
                model_name="test-speaker-model",
                expires_at=now - timedelta(seconds=1),
            )
        )
        db.commit()
        job = add_job(
            db,
            storage,
            school_id=school.id,
            teacher_id=teacher.id,
            kind=VoiceprintJobKind.verification,
        )
        job.created_at = now - timedelta(seconds=2)
        audio_paths = job_audio_paths(storage, job)
        db.commit()

        deleted_count = delete_expired_voiceprints(db=db, storage=storage, now=now)

        assert deleted_count == 1
        assert db.scalar(select(TeacherVoiceprint)) is None
        assert db.scalar(select(VoiceprintJob)) is None
        assert all(not path.exists() for path in audio_paths)

    engine.dispose()


def test_terminal_voiceprint_job_is_removed_after_its_retention_deadline(tmp_path):
    engine = create_database_engine(f"sqlite:///{tmp_path}/voiceprint.db")
    initialise_database(engine)
    Session = create_session_factory(engine)
    storage = CloudAudioJobStorage(job_dir=str(tmp_path / "jobs"), max_file_bytes=1024)
    now = utc_now()

    with Session() as db:
        school = School(name="短命ジョブ園")
        db.add(school)
        db.flush()
        teacher = Teacher(school_id=school.id, name="短命ジョブ先生")
        db.add(teacher)
        db.commit()
        job = add_job(
            db,
            storage,
            school_id=school.id,
            teacher_id=teacher.id,
            kind=VoiceprintJobKind.verification,
        )
        job.status = VoiceprintJobStatus.completed
        job.completed_at = now - timedelta(minutes=1)
        job.expires_at = now - timedelta(seconds=1)
        audio_paths = job_audio_paths(storage, job)
        job_id = job.id
        db.commit()

        assert expire_voiceprint_jobs(db=db, storage=storage, now=now) == 0
        assert db.get(VoiceprintJob, job_id) is None
        assert all(not path.exists() for path in audio_paths)

    engine.dispose()


def test_expired_voiceprint_cleanup_preserves_new_reenrollment_job(tmp_path):
    engine = create_database_engine(f"sqlite:///{tmp_path}/voiceprint.db")
    initialise_database(engine)
    Session = create_session_factory(engine)
    storage = CloudAudioJobStorage(job_dir=str(tmp_path / "jobs"), max_file_bytes=1024)
    now = utc_now()

    with Session() as db:
        school = School(name="再登録園")
        db.add(school)
        db.flush()
        teacher = Teacher(school_id=school.id, name="再登録先生")
        db.add(teacher)
        db.flush()
        db.add(
            TeacherVoiceprint(
                school_id=school.id,
                teacher_id=teacher.id,
                encrypted_embedding="expired",
                embedding_dimension=2,
                model_name="test-speaker-model",
                expires_at=now - timedelta(seconds=1),
            )
        )
        db.commit()
        job = add_job(
            db,
            storage,
            school_id=school.id,
            teacher_id=teacher.id,
            kind=VoiceprintJobKind.enrollment,
        )
        audio_paths = job_audio_paths(storage, job)

        assert delete_expired_voiceprints(db=db, storage=storage, now=now) == 1
        assert db.scalar(select(TeacherVoiceprint)) is None
        assert db.get(VoiceprintJob, job.id) is not None
        assert all(path.exists() for path in audio_paths)

    engine.dispose()


def test_voiceprint_crypto_and_similarity_reject_dimension_mismatch():
    key = Fernet.generate_key().decode("ascii")
    encrypted = encrypt_embedding([1.0, 0.0], key)

    assert decrypt_embedding(encrypted, key) == [1.0, 0.0]
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0


def test_voiceprint_averages_normalized_samples_into_one_template():
    averaged = average_embeddings([[3.0, 4.0], [6.0, 8.0], [0.0, 1.0]])

    assert len(averaged) == 2
    assert cosine_similarity(averaged, [0.4, 0.9166666667]) == pytest.approx(1.0)


def test_voiceprint_quality_failure_identifies_sample_and_deletes_all_audio(tmp_path):
    engine = create_database_engine(f"sqlite:///{tmp_path}/voiceprint.db")
    initialise_database(engine)
    Session = create_session_factory(engine)
    storage = CloudAudioJobStorage(job_dir=str(tmp_path / "jobs"), max_file_bytes=1024)
    now = utc_now()

    with Session() as db:
        school = School(name="品質確認園")
        db.add(school)
        db.flush()
        teacher = Teacher(school_id=school.id, name="品質確認先生")
        db.add(teacher)
        db.flush()
        db.add(
            VoiceEnrollmentConsent(
                school_id=school.id,
                teacher_id=teacher.id,
                purpose="teacher_voiceprint_enrollment",
                policy_version="test",
                retention_days=30,
                expires_at=now + timedelta(days=30),
            )
        )
        db.commit()
        job = add_job(
            db,
            storage,
            school_id=school.id,
            teacher_id=teacher.id,
            kind=VoiceprintJobKind.enrollment,
        )
        audio_paths = job_audio_paths(storage, job)
        quality_analyzer = FakeQualityAnalyzer(
            VoiceprintQualityIssue.multiple_speakers,
            issue_on_call=2,
        )
        extractor = FakeExtractor([1.0, 0.0])

        result = process_next_voiceprint_job(
            db=db,
            storage=storage,
            extractor=extractor,
            quality_analyzer=quality_analyzer,
            encryption_key=Fernet.generate_key().decode("ascii"),
            match_threshold=0.75,
        )

        assert result is not None
        assert result.status == VoiceprintJobStatus.failed
        assert result.quality_issue == VoiceprintQualityIssue.multiple_speakers.value
        assert result.quality_sample_index == 2
        assert quality_analyzer.calls == 2
        assert extractor.calls == 0
        assert all(not path.exists() for path in audio_paths)
        assert db.scalar(select(TeacherVoiceprint)) is None

    engine.dispose()
