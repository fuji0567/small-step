from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.dependencies import AuthenticatedUser, CurrentTeacher, get_current_teacher
from app.config import Settings
from app.database import create_database_engine, create_session_factory, initialise_database
from app.edge_audio import EdgeAudioCandidate, EdgeAudioProcessor, OpenAICompatibleSummarizer
from app.main import create_app
from app.models import Child, Notification, Record, RecordCategory, RecordStatus, School, Teacher, utc_now
from app.recorder_children import RecorderChildMatcher
from app.schemas import ChildCreate, ChildUpdate


def candidate(reference="園児候補_001"):
    return EdgeAudioCandidate(
        recordable=True, category=RecordCategory.growth, confidence=.9,
        summary="園児候補_001は五つ積めました。", subject_reference=reference,
    )


@pytest.fixture()
def db(tmp_path):
    engine = create_database_engine(f"sqlite:///{tmp_path}/children.db")
    initialise_database(engine)
    with create_session_factory(engine)() as session:
        yield session
    engine.dispose()


def child(db, *, name="山田 あおい", names=None, school="school", active=True):
    result = Child(school_id=school, display_name=name, recording_names=names or ["あおい", "青井"], is_active=active)
    db.add(result)
    db.commit()
    return result


def test_known_names_are_masked_and_only_a_reference_becomes_advice(db):
    target = child(db)
    matcher = RecorderChildMatcher(db=db, school_id="school")
    text = matcher.prepare("speaker_01: アオイちゃん、今日は五つ積めたね。")
    assert "園児候補_001ちゃん" in text
    assert "あおい" not in text and "アオイ" not in text
    result = matcher.process(candidate().model_copy(update={"conversation_prompt": "青井ちゃんとアオイちゃんのタワー"}))
    assert result.summary == "園児は五つ積めました。"
    assert "青井" not in result.conversation_prompt
    assert "アオイ" not in result.conversation_prompt and "タワー" in result.conversation_prompt
    assert result.subject_reference is None
    assert "subject_reference" not in result.record_payload()
    assert matcher.candidate(db) == target.id
    matcher.clear()
    assert not matcher.names and not matcher.matches and not matcher.references


@pytest.mark.parametrize("text,reference", [
    ("speaker_01: おはようございます。", None),
    ("speaker_01: あおいちゃん、片付けてね。", None),
    ("speaker_01: あおいちゃん、積めたね。", "園児候補_999"),
    ("speaker_01: はるあおいちゃんが積めたね。", "園児候補_001"),
    ("speaker_01: 園児候補_001が五つ積めたね。", "園児候補_001"),
])
def test_calling_name_or_unknown_or_injected_reference_is_not_enough(db, text, reference):
    child(db)
    matcher = RecorderChildMatcher(db=db, school_id="school")
    matcher.prepare(text)
    matcher.process(candidate(reference))
    assert matcher.candidate(db) is None


@pytest.mark.parametrize("other_active", [True, False])
def test_duplicate_names_including_archived_children_do_not_select(db, other_active):
    child(db)
    child(db, name="別の あおい", active=other_active)
    matcher = RecorderChildMatcher(db=db, school_id="school")
    assert "園児候補_" not in matcher.prepare("あおいちゃん、五つ積めたね。")
    matcher.process(candidate())
    assert matcher.candidate(db) is None


def test_other_school_and_archived_children_are_not_candidates(db):
    child(db, school="other")
    child(db, active=False)
    matcher = RecorderChildMatcher(db=db, school_id="school")
    matcher.prepare("あおいちゃん、五つ積めたね。")
    matcher.process(candidate())
    assert matcher.candidate(db) is None


def test_multiple_named_children_do_not_select_even_if_llm_returns_one(db):
    child(db)
    child(db, name="田中 はると", names=["はると"])
    matcher = RecorderChildMatcher(db=db, school_id="school")
    matcher.prepare("あおいちゃん、はるとくんが五つ積めたね。")
    matcher.process(candidate())
    assert matcher.candidate(db) is None


def test_different_subjects_across_segments_and_roster_changes_clear_advice(db):
    target = child(db)
    matcher = RecorderChildMatcher(db=db, school_id="school")
    matcher.prepare("あおいちゃん、五つ積めたね。")
    matcher.process(candidate())
    assert matcher.candidate(db) == target.id
    child(db, name="別の あおい")
    assert matcher.candidate(db) is None


def test_different_children_in_different_recordable_segments_remain_unselected(db):
    child(db)
    child(db, name="田中 はると", names=["はると"])
    matcher = RecorderChildMatcher(db=db, school_id="school")
    matcher.prepare("あおいちゃん、五つ積めたね。")
    matcher.process(candidate())
    matcher.prepare("はるとくん、走れたね。")
    matcher.process(candidate("園児候補_002"))
    assert matcher.candidate(db) is None


def test_recording_path_masks_names_before_llm_and_retains_audio_for_worker_cleanup(db, tmp_path):
    child(db)
    matcher = RecorderChildMatcher(db=db, school_id="school")
    audio = tmp_path / "private.webm"
    audio.write_bytes(b"private audio")
    class Transcriber:
        def transcribe(self, path, **kwargs):
            return "あおいちゃん、五つ積めたね。"
    class Summarizer:
        def summarize(self, text, **kwargs):
            assert "あおい" not in text
            assert "園児候補_001" in text
            return candidate()
    processor = EdgeAudioProcessor(settings=Settings(_env_file=None), transcriber=Transcriber(), summarizer=Summarizer())
    assert processor.analyze_trusted_recorder_audio_file(str(audio), child_matcher=matcher).summary == "園児は五つ積めました。"
    assert audio.exists()


def test_subject_inference_is_optional_and_does_not_expose_roster(monkeypatch):
    payloads = []
    def post(url, **kwargs):
        payloads.append(kwargs["json"])
        return httpx.Response(200, json={"choices": [{"message": {"content": candidate().model_dump_json()}}]})
    monkeypatch.setattr(httpx, "post", post)
    summarizer = OpenAICompatibleSummarizer(base_url="http://localhost:8001/v1", api_key=None, model="test", allow_external=False, timeout_seconds=1)
    assert summarizer.summarize("園児候補_001ちゃんが積めたね。").subject_reference == "園児候補_001"
    assert "呼ばれた相手と出来事の対象を混同しません" in payloads[0]["messages"][0]["content"]
    assert "subject_reference" in payloads[0]["messages"][0]["content"]


def test_recording_names_validation_and_configuration():
    assert ChildUpdate(display_name="園児", recording_names=[" あおい "]).recording_names == ["あおい"]
    for names in (["あ"], ["name_001"], ["あおい"] * 6, [" "]):
        with pytest.raises(ValueError):
            ChildCreate(school_id=uuid4(), display_name="園児", recording_names=names)
    with pytest.raises(ValueError):
        Settings(_env_file=None, recorder_child_matching_enabled=True)


@pytest.mark.parametrize("reference", [123, ["private name"], "private name", "園児候補_1234"])
def test_invalid_optional_reference_does_not_drop_a_usable_event(reference):
    result = EdgeAudioCandidate.model_validate({**candidate().model_dump(), "subject_reference": reference})
    assert result.recordable and result.subject_reference is None


def test_advice_requires_scope_and_human_confirmation_and_uses_chosen_child(tmp_path):
    app = create_app(Settings(_env_file=None, auth_mode="development", database_url=f"sqlite:///{tmp_path}/api.db", recorder_enabled=True, recorder_child_matching_enabled=True))
    with TestClient(app) as client:
        with app.state.session_factory() as session:
            school, other = School(name="test"), School(name="other")
            session.add_all([school, other]); session.flush()
            owner = Teacher(school_id=school.id, name="先生", email="teacher@example.test")
            outsider = Teacher(school_id=other.id, name="別園先生", email="other@example.test")
            session.add_all([owner, outsider]); session.flush()
            target = child(session, school=school.id)
            alternative = child(session, school=school.id, name="田中 はると", names=["はると"])
            record = Record(school_id=school.id, teacher_id=owner.id, child_id=None, candidate_child_id=target.id, source_event_id="recorder-session-test", category=RecordCategory.growth, status=RecordStatus.pending_review, confidence=.9, occurred_at=utc_now(), summary="園児は積めました。")
            session.add(record); session.commit()
            record_id, target_id, alternative_id = record.id, target.id, alternative.id
            app.dependency_overrides[get_current_teacher] = lambda: CurrentTeacher(AuthenticatedUser("test", owner.email), owner, False)
            assert client.get(f"/api/v1/records/{record_id}/child-suggestion").json()["child_id"] == target_id
            assert client.get(f"/api/v1/records/{record_id}").json()["child_id"] is None
            assert "candidate_child_id" not in client.get(f"/api/v1/records/{record_id}").json()
            assert client.post(f"/api/v1/records/{record_id}/approve", json={"child_id": target_id}).status_code == 422
            with app.state.session_factory() as check:
                assert not list(check.scalars(select(Notification)))
            app.dependency_overrides[get_current_teacher] = lambda: CurrentTeacher(AuthenticatedUser("other", outsider.email), outsider, False)
            assert client.get(f"/api/v1/records/{record_id}/child-suggestion").status_code == 403
            app.dependency_overrides[get_current_teacher] = lambda: CurrentTeacher(AuthenticatedUser("test", owner.email), owner, False)
            response = client.post(f"/api/v1/records/{record_id}/approve", json={"child_id": alternative_id, "child_confirmed": True})
            assert response.status_code == 200
            assert response.json()["child_id"] == alternative_id
            assert client.get(f"/api/v1/records/{record_id}/child-suggestion").json()["status"] == "unidentified"
