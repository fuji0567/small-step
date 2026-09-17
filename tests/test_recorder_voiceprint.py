from datetime import timedelta
from types import SimpleNamespace

import pytest
from cryptography.fernet import Fernet
from fastapi import HTTPException

from app.api.dependencies import AuthenticatedUser, CurrentTeacher
from app.api.routes import get_record_voiceprint_suggestion, grant_my_voice_consent
from app.database import create_database_engine, create_session_factory, initialise_database
from app.models import (
    Record, RecordCategory, School, Teacher, TeacherVoiceprint, VoiceEnrollmentConsent, utc_now,
)
from app.recorder_voiceprint import RecorderVoiceprintMatcher, choose_match, clean_intervals, eligible_voiceprints
from app.speaker_diarization import SpeakerDiarizationResult, SpeakerSegment
from app.voiceprint import encrypt_embedding
from app.schemas import VoiceConsentCreate


@pytest.fixture
def enrollment(tmp_path):
    engine = create_database_engine(f"sqlite:///{tmp_path}/matching.db")
    initialise_database(engine)
    with create_session_factory(engine)() as db:
        school = School(name="Test")
        db.add(school)
        db.flush()
        teacher = Teacher(school_id=school.id, name="Test teacher", email="test@example.test")
        db.add(teacher)
        db.flush()
        key = Fernet.generate_key().decode()
        consent = VoiceEnrollmentConsent(
            teacher_id=teacher.id, school_id=school.id, purpose="teacher_voiceprint_enrollment",
            policy_version="test", retention_days=30, allows_recorder_identification=True,
            expires_at=utc_now() + timedelta(days=30),
        )
        voiceprint = TeacherVoiceprint(
            teacher_id=teacher.id, school_id=school.id, model_name="test-model",
            encrypted_embedding=encrypt_embedding([1, 0], key), embedding_dimension=2,
            expires_at=utc_now() + timedelta(days=30),
        )
        db.add_all([consent, voiceprint])
        db.commit()
        yield db, school, teacher, consent, voiceprint, key
    engine.dispose()


@pytest.mark.parametrize("change", ["optout", "revoked", "consent_expired", "template_expired", "disabled", "model", "purpose"])
def test_only_explicit_active_matching_consent_is_eligible(enrollment, change):
    db, school, teacher, consent, voiceprint, key = enrollment
    assert len(eligible_voiceprints(db, school.id, "test-model")) == 1
    if change == "optout":
        consent.allows_recorder_identification = False
    elif change == "revoked":
        consent.revoked_at = utc_now()
    elif change == "consent_expired":
        consent.expires_at = utc_now() - timedelta(seconds=1)
    elif change == "template_expired":
        voiceprint.expires_at = utc_now() - timedelta(seconds=1)
    elif change == "disabled":
        teacher.is_active = False
    elif change == "model":
        voiceprint.model_name = "other"
    else:
        consent.purpose = "other"
    db.commit()
    assert eligible_voiceprints(db, school.id, "test-model") == []


def test_other_school_and_mismatched_school_metadata_are_excluded(enrollment):
    db, school, teacher, consent, voiceprint, key = enrollment
    other = School(name="Other")
    db.add(other)
    db.commit()
    assert eligible_voiceprints(db, other.id, "test-model") == []
    consent.school_id = other.id
    db.commit()
    assert eligible_voiceprints(db, school.id, "test-model") == []


def test_low_score_ties_and_near_ties_do_not_identify():
    assert choose_match([1, 0], [], threshold=.85, margin=.1) is None
    assert choose_match([1, 0], [("one", [0, 1])], threshold=.85, margin=.1) is None
    assert choose_match([1, 0], [("one", [1, 0]), ("two", [1, .01])], threshold=.85, margin=.1) is None
    assert choose_match([1, 0], [("one", [1, 0]), ("two", [0, 1])], threshold=.85, margin=.1) == "one"


def test_overlap_is_removed_even_from_exclusive_speaker_intervals():
    result = SpeakerDiarizationResult(speaker_count=1, segments=[SpeakerSegment(
        speaker_label="speaker_01", start_seconds=0, end_seconds=10,
    )], overlap_intervals=[(2, 4), (8, 10)])
    assert list(clean_intervals(result, "speaker_01")) == [(0, 2), (4, 8)]


def test_same_speaker_duplicate_intervals_do_not_inflate_speech_duration():
    result = SpeakerDiarizationResult(speaker_count=1, segments=[SpeakerSegment(
        speaker_label="speaker_01", start_seconds=0, end_seconds=2,
    )] * 3)
    assert list(clean_intervals(result, "speaker_01")) == [(0, 2)]


def make_matcher(enrollment, extractor=None):
    db, school, teacher, consent, voiceprint, key = enrollment
    return RecorderVoiceprintMatcher(
        db=db, school_id=school.id, extractor=extractor or SimpleNamespace(model_name="test-model"),
        encryption_key=key, threshold=.85, margin=.1,
    )


def test_multiple_teachers_and_consent_changed_during_processing_are_unidentified(enrollment):
    db, school, teacher, consent, voiceprint, key = enrollment
    matcher = make_matcher(enrollment)
    matcher.matches.add(teacher.id)
    assert matcher.candidate() == teacher.id
    matcher.matches.add("other")
    assert matcher.candidate() is None
    matcher.matches.remove("other")
    consent.consented_at = utc_now() + timedelta(seconds=1)
    db.commit()
    assert matcher.candidate() is None


@pytest.mark.parametrize("seconds,amplitude,expected", [(2, .1, False), (20, .1, True), (5, .001, False), (5, 1., False)])
def test_in_memory_excerpts_are_bounded_and_deleted(enrollment, monkeypatch, seconds, amplitude, expected):
    torch = pytest.importorskip("torch")
    Audio = pytest.importorskip("pyannote.audio.core.io").Audio
    waveform = torch.full((1, 20 * 16000), amplitude)
    monkeypatch.setattr(Audio, "__call__", lambda self, path: (waveform, 16000))
    vectors = []
    excerpts = []

    class Extractor:
        model_name = "test-model"

        def extract_waveform(self, excerpt, rate):
            assert not enrollment[0].in_transaction()
            assert 3 * rate <= excerpt.shape[-1] <= 10 * rate
            excerpts.append(excerpt)
            vector = [1, 0]
            vectors.append(vector)
            return vector

    matcher = make_matcher(enrollment, Extractor())
    matcher.observe("unused.wav", SpeakerDiarizationResult(speaker_count=1, segments=[SpeakerSegment(
        speaker_label="speaker_01", start_seconds=0, end_seconds=seconds,
    )]))
    assert matcher.candidate() == (enrollment[2].id if expected else None)
    assert vectors == ([[]] if expected else [])
    assert torch.count_nonzero(waveform) == 0
    assert all(torch.count_nonzero(excerpt) == 0 for excerpt in excerpts)


def test_corrupt_template_fails_closed_without_logging_secrets(enrollment, capsys):
    db, school, teacher, consent, voiceprint, key = enrollment
    voiceprint.encrypted_embedding = "private-template-secret"
    db.commit()
    matcher = make_matcher(enrollment)
    matcher.matches.add(teacher.id)
    matcher.observe("private-audio-path", SpeakerDiarizationResult(speaker_count=0, segments=[]))
    assert matcher.failed and matcher.candidate() is None
    assert "private" not in capsys.readouterr().out


def test_suggestion_endpoint_rechecks_scope_and_consent(enrollment):
    db, school, teacher, consent, voiceprint, key = enrollment
    record = Record(
        school_id=school.id, teacher_id=teacher.id, category=RecordCategory.growth,
        confidence=.9, occurred_at=utc_now(), summary="Anonymous",
        voiceprint_matching_checked=True, voiceprint_candidate_teacher_id=teacher.id,
    )
    db.add(record)
    db.commit()
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(settings=SimpleNamespace(
        voiceprint_enabled=True, recorder_voiceprint_matching_enabled=True, voiceprint_model="test-model",
    ))))
    current = CurrentTeacher(AuthenticatedUser("test", teacher.email), teacher, False)
    result = get_record_voiceprint_suggestion(record.id, request, current, db)
    assert result.status == "candidate" and str(result.teacher_id) == teacher.id
    consent.allows_recorder_identification = False
    db.commit()
    assert get_record_voiceprint_suggestion(record.id, request, current, db).status == "unidentified"
    outsider = Teacher(school_id="other-school", name="Other", email="other@test")
    with pytest.raises(HTTPException) as error:
        get_record_voiceprint_suggestion(record.id, request, CurrentTeacher(current.user, outsider, False), db)
    assert error.value.status_code == 403
    assert record.teacher_id == teacher.id


def test_consent_optout_clears_existing_suggestion_without_deleting_enrollment(enrollment):
    db, school, teacher, consent, voiceprint, key = enrollment
    record = Record(
        school_id=school.id, teacher_id=teacher.id, category=RecordCategory.growth,
        confidence=.9, occurred_at=utc_now(), summary="Anonymous",
        voiceprint_matching_checked=True, voiceprint_candidate_teacher_id=teacher.id,
    )
    db.add(record)
    db.commit()
    current = CurrentTeacher(AuthenticatedUser("test", teacher.email), teacher, False)
    result = grant_my_voice_consent(VoiceConsentCreate(accepts_voiceprint_enrollment=True), current, db)
    db.refresh(record)
    assert not result.allows_recorder_identification
    assert record.voiceprint_candidate_teacher_id is None
    assert db.get(TeacherVoiceprint, voiceprint.id) is not None


def test_recorder_observer_receives_existing_diarization_without_changing_summary(tmp_path):
    from app.config import Settings
    from app.edge_audio import EdgeAudioCandidate, EdgeAudioProcessor, TranscriptionResult
    path = tmp_path / "test.wav"
    path.write_bytes(b"RIFF-test")
    diarization = SpeakerDiarizationResult(speaker_count=1, segments=[])
    candidate = EdgeAudioCandidate(recordable=True, category=RecordCategory.growth, confidence=.9, summary="Anonymous")
    transcriber = SimpleNamespace(transcribe_with_metadata=lambda *args, **kwargs: TranscriptionResult(
        transcript="temporary transcript", diarization=diarization,
    ))
    processor = EdgeAudioProcessor(
        settings=Settings(_env_file=None), transcriber=transcriber,
        summarizer=SimpleNamespace(summarize=lambda *args, **kwargs: candidate),
    )
    observed = []
    assert processor.analyze_trusted_recorder_audio_file(str(path), speaker_observer=lambda *args: observed.append(args)) == candidate
    assert observed == [(path.resolve(), diarization)]


def test_waveform_embedding_adapter_uses_in_memory_input():
    from app.voiceprint import PyannoteVoiceprintExtractor
    extractor = PyannoteVoiceprintExtractor(model_name="test", token="test", device="cpu")
    waveform = object()
    def inference(audio):
        assert audio == {"waveform": waveform, "sample_rate": 16000}
        return [[3, 4]]
    extractor._inference = inference
    assert extractor.extract_waveform(waveform, 16000) == [.6, .8]


def test_expired_consent_clears_suggestions_even_before_template_expiry(enrollment, tmp_path):
    from app.cloud_audio import CloudAudioJobStorage
    from app.voiceprint_worker import delete_expired_voiceprints
    db, school, teacher, consent, voiceprint, key = enrollment
    record = Record(
        school_id=school.id, teacher_id=teacher.id, category=RecordCategory.growth,
        confidence=.9, occurred_at=utc_now(), summary="Anonymous",
        voiceprint_matching_checked=True, voiceprint_candidate_teacher_id=teacher.id,
    )
    db.add(record)
    consent.expires_at = utc_now() - timedelta(seconds=1)
    db.commit()
    assert delete_expired_voiceprints(db=db, storage=CloudAudioJobStorage(
        job_dir=str(tmp_path / "audio"), max_file_bytes=1024,
    )) == 0
    db.refresh(record)
    assert record.voiceprint_candidate_teacher_id is None
