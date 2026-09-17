import asyncio
import hashlib
import io
import os
import sys
from threading import Event
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import UploadFile
from sqlalchemy import select

from app.database import create_database_engine, create_session_factory, initialise_database
from app.edge_audio import EdgeAudioCandidate, EdgeAudioError, EdgeAudioProcessor, NoSpeechDetectedError
from app.config import Settings
from app.models import (
    Notification, Record, RecordCategory, RecordStatus, RecordingSegment,
    RecordingSession, RecordingSessionStatus, School, Teacher, utc_now,
)
from app.recorder import RecorderStorage, RecorderStorageError
from app.recorder_worker import (
    RecorderMaintenance, claim_next_recorder_session, cleanup_recorder_sessions,
    process_next_recorder_session,
)


def event(summary="Anonymous growth", category=RecordCategory.growth):
    return EdgeAudioCandidate(recordable=True, category=category, confidence=0.9, summary=summary)


def test_failure_diagnostics_do_not_include_private_exception_content(capsys):
    from app.recorder_worker import _log_processing_failure

    inner = ModuleNotFoundError("private-name /private/audio.wav secret-token")
    outer = EdgeAudioError("private transcript")
    outer.__cause__ = inner
    _log_processing_failure("audio_analysis", outer)
    output = capsys.readouterr().out
    assert "stage=audio_analysis" in output
    assert "EdgeAudioError/ModuleNotFoundError" in output
    assert "private" not in output
    assert "secret-token" not in output


def test_failure_diagnostics_hide_unknown_exception_names(capsys):
    from app.recorder_worker import _log_processing_failure

    error = type("PrivateTeacherName", (Exception,), {})("secret")
    error.__cause__ = error
    _log_processing_failure("audio_analysis", error)
    assert "types=OtherError" in capsys.readouterr().out


@pytest.fixture()
def runtime(tmp_path):
    engine = create_database_engine(f"sqlite:///{tmp_path}/worker.db")
    initialise_database(engine)
    factory = create_session_factory(engine)
    storage = RecorderStorage(session_dir=str(tmp_path / "audio"), max_segment_bytes=1024)
    storage.ensure_directory()
    with factory() as db:
        school = School(name="Worker school")
        db.add(school)
        db.flush()
        teacher = Teacher(school_id=school.id, name="Owner", email="owner@example.test")
        db.add(teacher)
        db.commit()
        owner = (school.id, teacher.id)
    yield factory, storage, owner
    engine.dispose()


def enqueue(runtime, *, count=3, status=RecordingSessionStatus.queued):
    factory, storage, (school_id, teacher_id) = runtime
    with factory() as db:
        recording = RecordingSession(
            school_id=school_id, teacher_id=teacher_id, client_session_id=str(uuid4()),
            status=status, expires_at=utc_now() + timedelta(hours=24),
        )
        db.add(recording)
        db.flush()
        session_id = recording.id
        for sequence in reversed(range(count)):
            content = f"private audio {sequence}".encode()
            key, size, sha256 = asyncio.run(storage.store_upload(
                upload=UploadFile(file=io.BytesIO(content)), session_id=session_id,
                expected_sha256=hashlib.sha256(content).hexdigest(), media_type="audio/webm",
            ))
            db.add(RecordingSegment(
                session_id=session_id, sequence=sequence, storage_key=key,
                size_bytes=size, sha256=sha256, duration_ms=60_000, media_type="audio/webm",
            ))
        db.commit()
    return session_id


class Processor:
    def __init__(self, db, *, failing=(), no_event=False, merge_failure=False, hook=None, injury=False):
        self.db = db
        self.failing = failing
        self.no_event = no_event
        self.merge_failure = merge_failure
        self.hook = hook
        self.injury = injury
        self.sequences = []
        self.merges = []

    def analyze_trusted_recorder_audio_file(self, audio_path):
        assert not self.db.in_transaction(), "Inference must not hold a database transaction"
        path = Path(audio_path)
        sequence = int(path.read_bytes().decode().rsplit(" ", 1)[1])
        self.sequences.append(sequence)
        if self.hook:
            self.hook(sequence)
        if sequence in self.failing:
            assert path.is_file(), "Retries need their original segment"
            raise EdgeAudioError("private exception must not be logged")
        if self.no_event:
            return EdgeAudioCandidate(recordable=False, category=None, confidence=0, summary=None)
        return event(f"Anonymous event {sequence}", RecordCategory.injury if self.injury else RecordCategory.growth)

    def merge_recorder_candidates(self, previous, following):
        assert not self.db.in_transaction()
        self.merges.append((previous.summary, following.summary))
        if self.merge_failure:
            raise EdgeAudioError("private merge exception")
        return event(f"{previous.summary}; {following.summary}")


def test_ordered_processing_creates_only_one_pending_record_and_removes_audio(runtime):
    factory, storage, (school_id, teacher_id) = runtime
    session_id = enqueue(runtime)
    with factory() as db:
        processor = Processor(db)
        result = process_next_recorder_session(db=db, storage=storage, processor=processor)
        assert result.status == RecordingSessionStatus.completed
        assert result.processed_segment_count == 3
        assert result.failed_segment_count == 0
        assert result.claim_token is None
        record = db.get(Record, result.record_id)
        assert record.school_id == school_id and record.teacher_id == teacher_id
        assert record.child_id is None
        assert record.status == RecordStatus.pending_review
        assert record.audio_processing_incomplete is False
        assert record.summary == "Anonymous event 0; Anonymous event 1; Anonymous event 2"
        assert record.source_event_id == f"recorder-session-{session_id}"
        assert list(db.scalars(select(Notification))) == []
        assert processor.sequences == [0, 1, 2]
        assert len(processor.merges) == 2
        assert process_next_recorder_session(db=db, storage=storage, processor=processor) is None
        assert len(list(db.scalars(select(Record)))) == 1
        assert "private audio" not in record.summary
    assert not storage.session_path(session_id).exists()


@pytest.mark.parametrize("failing,expected", [((1,), "completed"), ((0, 1, 2), "failed")])
def test_segment_retry_partial_warning_and_total_failure(runtime, failing, expected, capsys):
    factory, storage, _owner = runtime
    session_id = enqueue(runtime)
    with factory() as db:
        processor = Processor(db, failing=failing)
        result = process_next_recorder_session(db=db, storage=storage, processor=processor)
        assert result.status.value == expected
        assert result.processed_segment_count == 3
        assert result.failed_segment_count == len(failing)
        for sequence in failing:
            assert processor.sequences.count(sequence) == 2
        if expected == "completed":
            record = db.get(Record, result.record_id)
            assert record.audio_processing_incomplete is True
            assert record.summary == "Anonymous event 0; Anonymous event 2"
        else:
            assert result.record_id is None
            assert list(db.scalars(select(Record))) == []
    assert not storage.session_path(session_id).exists()
    assert "private" not in capsys.readouterr().out


def test_no_concrete_event_completes_without_record(runtime):
    factory, storage, _owner = runtime
    session_id = enqueue(runtime)
    with factory() as db:
        result = process_next_recorder_session(db=db, storage=storage, processor=Processor(db, no_event=True))
        assert result.status == RecordingSessionStatus.completed
        assert result.record_id is None
        assert result.failed_segment_count == 0
    assert not storage.session_path(session_id).exists()


def test_silence_is_not_treated_as_a_model_failure(runtime):
    factory, storage, _owner = runtime
    session_id = enqueue(runtime, count=1)
    class SilentProcessor:
        def analyze_trusted_recorder_audio_file(self, _path):
            raise NoSpeechDetectedError("no spoken content")
    with factory() as db:
        result = process_next_recorder_session(db=db, storage=storage, processor=SilentProcessor())
        assert result.status == RecordingSessionStatus.completed
        assert result.failed_segment_count == 0
        assert result.record_id is None
    assert not storage.session_path(session_id).exists()


@pytest.mark.parametrize("injury,expected", [(False, "completed"), (True, "failed")])
def test_failed_merge_warns_but_does_not_publish_incomplete_known_injuries(runtime, injury, expected):
    factory, storage, _owner = runtime
    session_id = enqueue(runtime, count=2)
    with factory() as db:
        processor = Processor(db, merge_failure=True, injury=injury)
        result = process_next_recorder_session(db=db, storage=storage, processor=processor)
        assert result.status.value == expected
        assert len(processor.merges) == 2
        if injury:
            assert list(db.scalars(select(Record))) == []
        else:
            assert db.get(Record, result.record_id).audio_processing_incomplete is True
            assert result.failed_segment_count == 1
    assert not storage.session_path(session_id).exists()


@pytest.mark.parametrize("change", ["inactive", "wrong_school"])
def test_unavailable_owner_is_not_processed(runtime, change):
    factory, storage, (_school_id, teacher_id) = runtime
    session_id = enqueue(runtime)
    with factory() as db:
        teacher = db.get(Teacher, teacher_id)
        if change == "inactive":
            teacher.is_active = False
        else:
            school = School(name="Other school")
            db.add(school)
            db.flush()
            teacher.school_id = school.id
        db.commit()
        processor = Processor(db)
        result = process_next_recorder_session(db=db, storage=storage, processor=processor)
        assert result.status == RecordingSessionStatus.failed
        assert processor.sequences == []
    assert not storage.session_path(session_id).exists()


@pytest.mark.parametrize("change", ["hash", "size", "gap", "duration", "missing"])
def test_invalid_segments_never_reach_inference(runtime, change):
    factory, storage, _owner = runtime
    session_id = enqueue(runtime, count=1)
    with factory() as db:
        segment = db.scalar(select(RecordingSegment).where(RecordingSegment.session_id == session_id))
        if change == "hash":
            segment.sha256 = "0" * 64
        elif change == "size":
            segment.size_bytes += 1
        elif change == "gap":
            segment.sequence = 1
        elif change == "duration":
            segment.duration_ms = 3_600_001
        else:
            storage.delete(segment.storage_key)
        db.commit()
        processor = Processor(db)
        result = process_next_recorder_session(db=db, storage=storage, processor=processor)
        assert result.status == RecordingSessionStatus.failed
        assert processor.sequences == []
        assert list(db.scalars(select(Record))) == []
    assert not storage.session_path(session_id).exists()


def test_cross_session_key_never_reads_or_deletes_other_audio(runtime):
    factory, storage, _owner = runtime
    first_id = enqueue(runtime, count=1)
    other_id = enqueue(runtime, count=1, status=RecordingSessionStatus.draft)
    with factory() as db:
        first = db.scalar(select(RecordingSegment).where(RecordingSegment.session_id == first_id))
        other = db.scalar(select(RecordingSegment).where(RecordingSegment.session_id == other_id))
        key = other.storage_key
        # A unique filename below the other session exercises the worker's owner check.
        first.storage_key = f"{other_id}/foreign.webm"
        storage.path_for(first.storage_key).write_bytes(b"private audio 0")
        db.commit()
        processor = Processor(db)
        result = process_next_recorder_session(db=db, storage=storage, processor=processor)
        assert result.status == RecordingSessionStatus.failed
        assert processor.sequences == []
        assert storage.path_for(key).is_file()
        assert storage.path_for(f"{other_id}/foreign.webm").is_file()
    assert not storage.session_path(first_id).exists()


def test_claim_is_exclusive_and_does_not_reclaim_processing_work(runtime):
    factory, _storage, _owner = runtime
    session_id = enqueue(runtime)
    with factory() as first, factory() as second:
        claimed = claim_next_recorder_session(db=first)
        assert claimed.id == session_id and claimed.claim_token
        assert claim_next_recorder_session(db=second) is None


@pytest.mark.parametrize("status", [RecordingSessionStatus.draft, RecordingSessionStatus.queued, RecordingSessionStatus.processing])
def test_expiry_cleans_audio_without_an_api_request(runtime, status):
    factory, storage, _owner = runtime
    session_id = enqueue(runtime, status=status)
    with factory() as db:
        recording = db.get(RecordingSession, session_id)
        recording.expires_at = utc_now() - timedelta(seconds=1)
        recording.claim_token = str(uuid4())
        db.commit()
        assert cleanup_recorder_sessions(db=db, storage=storage) == 1
        db.expire_all()
        assert db.get(RecordingSession, session_id).status == RecordingSessionStatus.expired
        assert db.get(RecordingSession, session_id).claim_token is None
    assert not storage.session_path(session_id).exists()


def test_crashed_processing_is_failed_not_replayed(runtime):
    factory, storage, _owner = runtime
    session_id = enqueue(runtime, status=RecordingSessionStatus.processing)
    with factory() as db:
        recording = db.get(RecordingSession, session_id)
        recording.updated_at = utc_now() - timedelta(minutes=11)
        recording.processed_segment_count = 1
        db.commit()
        processor = Processor(db)
        assert process_next_recorder_session(db=db, storage=storage, processor=processor) is None
        assert db.get(RecordingSession, session_id).status == RecordingSessionStatus.failed
        assert processor.sequences == []
    assert not storage.session_path(session_id).exists()


def test_expiry_during_inference_prevents_stale_record_creation(runtime):
    factory, storage, _owner = runtime
    session_id = enqueue(runtime, count=1)
    def expire(_sequence):
        with factory() as maintenance:
            cleanup_recorder_sessions(db=maintenance, storage=storage, now=utc_now() + timedelta(days=2))
    with factory() as db:
        processor = Processor(db, hook=expire)
        assert process_next_recorder_session(db=db, storage=storage, processor=processor) is None
        assert list(db.scalars(select(Record))) == []
        assert db.get(RecordingSession, session_id).status == RecordingSessionStatus.expired
    assert not storage.session_path(session_id).exists()


def test_owner_disabled_during_inference_prevents_record_creation(runtime):
    factory, storage, (_school_id, teacher_id) = runtime
    session_id = enqueue(runtime, count=1)
    def disable(_sequence):
        with factory() as other:
            other.get(Teacher, teacher_id).is_active = False
            other.commit()
    with factory() as db:
        result = process_next_recorder_session(db=db, storage=storage, processor=Processor(db, hook=disable))
        assert result.status == RecordingSessionStatus.failed
        assert list(db.scalars(select(Record))) == []
    assert not storage.session_path(session_id).exists()


def test_cleanup_retries_terminal_files_and_only_expires_old_orphans(runtime, monkeypatch):
    factory, storage, _owner = runtime
    session_id = enqueue(runtime, status=RecordingSessionStatus.failed)
    old_id, new_id = str(uuid4()), str(uuid4())
    for orphan in (old_id, new_id):
        storage.session_path(orphan).mkdir()
        (storage.session_path(orphan) / "orphan.webm").write_bytes(b"private orphan")
    old_time = (utc_now() - timedelta(days=2)).timestamp()
    os.utime(storage.session_path(old_id), (old_time, old_time))
    delete = storage.delete_session
    calls = 0
    def flaky(value):
        nonlocal calls
        if value == session_id and calls == 0:
            calls += 1
            raise OSError("private path must not appear in output")
        delete(value)
    monkeypatch.setattr(storage, "delete_session", flaky)
    with factory() as db:
        cleanup_recorder_sessions(db=db, storage=storage)
        assert storage.session_path(session_id).exists()
        cleanup_recorder_sessions(db=db, storage=storage)
    assert not storage.session_path(session_id).exists()
    assert not storage.session_path(old_id).exists()
    assert storage.session_path(new_id).exists()


def test_private_storage_permissions_and_symlink_guard(runtime, tmp_path):
    _factory, storage, _owner = runtime
    session_id = enqueue(runtime, count=1)
    assert storage.session_dir.stat().st_mode & 0o777 == 0o700
    directory = storage.session_path(session_id)
    assert directory.stat().st_mode & 0o777 == 0o700
    assert next(directory.iterdir()).stat().st_mode & 0o777 == 0o600
    outside = tmp_path / "outside"
    outside.mkdir()
    secret = outside / "keep.webm"
    secret.write_bytes(b"private")
    symlink_id = str(uuid4())
    (storage.session_dir / symlink_id).symlink_to(outside, target_is_directory=True)
    with pytest.raises(RecorderStorageError):
        storage.delete_session(symlink_id)
    assert secret.read_bytes() == b"private"


def test_recorder_analysis_retains_file_for_worker_retry(tmp_path):
    audio = tmp_path / "input.webm"
    audio.write_bytes(b"private")
    class Transcriber:
        def transcribe(self, path, **_kwargs):
            return "private transcript"
    class Summarizer:
        def summarize(self, text, **_kwargs):
            assert text == "private transcript"
            return event()
    processor = EdgeAudioProcessor(
        settings=Settings(edge_audio_delete_after_processing=True),
        transcriber=Transcriber(), summarizer=Summarizer(),
    )
    assert processor.analyze_trusted_recorder_audio_file(str(audio)).recordable
    assert audio.exists()


def test_merge_uses_only_anonymous_candidates_preserves_injury_and_lowest_confidence():
    class Summarizer:
        def summarize(self, text, **_kwargs):
            assert "Anonymous growth" in text and "Anonymous injury" in text
            assert "private transcript" not in text
            return event().model_copy(update={"confidence": 0.8})
    processor = EdgeAudioProcessor(settings=Settings(), summarizer=Summarizer())
    merged = processor.merge_recorder_candidates(event(), event("Anonymous injury", RecordCategory.injury))
    assert merged.category == RecordCategory.injury
    assert merged.confidence == 0.8


def test_maintenance_cleans_expired_sessions_on_startup(runtime):
    factory, storage, _owner = runtime
    session_id = enqueue(runtime, status=RecordingSessionStatus.draft)
    with factory() as db:
        db.get(RecordingSession, session_id).expires_at = utc_now() - timedelta(seconds=1)
        db.commit()
    with RecorderMaintenance(
        session_factory=factory, storage=storage, interval_seconds=60,
        processing_timeout=timedelta(minutes=10), orphan_retention=timedelta(hours=24),
    ):
        assert not storage.session_path(session_id).exists()


def test_background_maintenance_runs_while_inference_is_blocked(runtime):
    factory, storage, _owner = runtime
    session_id = enqueue(runtime, count=1)
    removed = Event()
    class ObservedStorage(RecorderStorage):
        def delete_session(self, value):
            super().delete_session(value)
            if value == session_id:
                removed.set()
    observed = ObservedStorage(session_dir=str(storage.session_dir), max_segment_bytes=1024)
    def block(_sequence):
        with factory() as other:
            other.get(RecordingSession, session_id).expires_at = utc_now() - timedelta(seconds=1)
            other.commit()
        assert removed.wait(5), "Cleanup must not wait for inference to return"
    with RecorderMaintenance(
        session_factory=factory, storage=observed, interval_seconds=0.05,
        processing_timeout=timedelta(minutes=10), orphan_retention=timedelta(hours=24),
    ), factory() as db:
        assert process_next_recorder_session(db=db, storage=observed, processor=Processor(db, hook=block)) is None
        assert list(db.scalars(select(Record))) == []


def test_interrupted_worker_removes_audio_then_stale_session_is_failed(runtime):
    factory, storage, _owner = runtime
    session_id = enqueue(runtime, count=1)
    def interrupt(_sequence):
        raise KeyboardInterrupt()
    with factory() as db:
        with pytest.raises(KeyboardInterrupt):
            process_next_recorder_session(db=db, storage=storage, processor=Processor(db, hook=interrupt))
        assert not storage.session_path(session_id).exists()
        cleanup_recorder_sessions(db=db, storage=storage, now=utc_now() + timedelta(minutes=11))
        assert db.get(RecordingSession, session_id).status == RecordingSessionStatus.failed
        assert list(db.scalars(select(Record))) == []


@pytest.mark.parametrize("enabled", [True, False])
def test_gpu_worker_once_consumes_recorder_sessions_only_when_enabled(runtime, monkeypatch, capsys, enabled):
    from scripts import process_cloud_audio_jobs as worker
    factory, storage, _owner = runtime
    session_id = enqueue(runtime, count=1)
    settings = Settings(
        database_url=str(factory.kw["bind"].url), cloud_audio_enabled=True, recorder_enabled=enabled,
        cloud_audio_job_dir=str(storage.session_dir.parent / "cloud"),
        recorder_session_dir=str(storage.session_dir), voiceprint_enabled=False,
        llm_base_url="http://127.0.0.1:8001/v1", llm_model="test",
    )
    class Processor:
        def status(self):
            return {"llm_configured": True}
        def analyze_trusted_recorder_audio_file(self, path):
            assert Path(path).is_file()
            return event()
    monkeypatch.setattr(worker, "Settings", lambda: settings)
    monkeypatch.setattr(worker, "EdgeAudioProcessor", lambda **_kwargs: Processor())
    monkeypatch.setattr(worker, "process_available_jobs", lambda **_kwargs: 0)
    monkeypatch.setattr(sys, "argv", ["process_cloud_audio_jobs.py", "--once"])
    worker.main()
    with factory() as db:
        result = db.get(RecordingSession, session_id)
        assert result.status == (RecordingSessionStatus.completed if enabled else RecordingSessionStatus.queued)
        assert (result.record_id is not None) is enabled
    output = capsys.readouterr().out
    assert ("1件" if enabled else "0件") in output and "private" not in output
    assert session_id not in output
    assert storage.session_path(session_id).exists() is not enabled
