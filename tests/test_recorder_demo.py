import json
import os
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from pydantic import ValidationError

from app.config import Settings
from app.edge_audio import EdgeAudioError, EdgeAudioProcessor, NoSpeechDetectedError, OpenAICompatibleSummarizer
from app.recorder_demo import DemoTrace, RecorderDemoStorage, cleanup_demo_files


def test_demo_storage_encrypts_and_expires_without_read_extending_ttl(tmp_path, monkeypatch):
    key = Fernet.generate_key().decode()
    storage = RecorderDemoStorage(tmp_path / "sessions", key)
    session_id = str(uuid4())
    storage.grant(session_id)
    assert storage.requested(session_id)
    trace = DemoTrace()
    trace.observe("transcript", "架空の園児の生の会話")
    storage.publish(session_id, trace, outcome="no_record", record_id=None)
    path = storage.directory / f"{session_id}.trace"
    assert "架空".encode() not in path.read_bytes()
    assert path.stat().st_mode & 0o777 == 0o600
    assert not storage.requested(session_id)
    data = storage.read(session_id)
    assert data["events"][0]["text"] == "架空の園児の生の会話"
    assert storage.read(session_id)["expires_at"] == data["expires_at"]
    monkeypatch.setattr("app.recorder_demo.time.time", lambda: data["expires_at"] + 1)
    assert storage.read(session_id) is None
    assert not path.exists()


def test_demo_requires_grant_and_caps_content(tmp_path):
    storage = RecorderDemoStorage(tmp_path / "sessions", Fernet.generate_key().decode())
    session_id = str(uuid4())
    trace = DemoTrace()
    for _ in range(100):
        trace.observe("transcript", "あ" * 20000)
    assert trace.truncated
    assert len(trace.events) < 40
    storage.publish(session_id, trace, outcome="no_record", record_id=None)
    assert storage.read(session_id) is None
    storage.grant(session_id)
    storage.publish(session_id, trace, outcome="no_record", record_id=None)
    assert storage.read(session_id)["truncated"]
    trace.clear()
    assert not trace.events


def test_demo_cleanup_runs_without_decryption_key(tmp_path):
    storage = RecorderDemoStorage(tmp_path / "sessions", Fernet.generate_key().decode())
    session_id = str(uuid4())
    storage.grant(session_id)
    trace = DemoTrace()
    storage.publish(session_id, trace, outcome="failed", record_id=None)
    path = storage.directory / f"{session_id}.trace"
    os.utime(path, (1, 1))
    cleanup_demo_files(tmp_path / "sessions", now=1000)
    assert not path.exists()


def test_demo_silence_shows_llm_was_not_called(tmp_path):
    class SilentTranscriber:
        def transcribe(self, *args, **kwargs):
            raise NoSpeechDetectedError("private decoder input")
    class UnexpectedSummarizer:
        def summarize(self, *args, **kwargs):
            raise AssertionError("Silence must not invoke the LLM")
    processor = EdgeAudioProcessor(settings=Settings(_env_file=None),
        transcriber=SilentTranscriber(), summarizer=UnexpectedSummarizer())
    path = tmp_path / "audio.mp4"
    path.write_bytes(b"mock audio")
    demo = DemoTrace()
    candidate = processor.analyze_trusted_recorder_audio_file(str(path), demo_observer=demo.observe)
    assert not candidate.recordable
    assert [event["kind"] for event in demo.events] == ["transcript", "decision"]
    assert "省略" in demo.events[1]["text"]
    assert "private" not in json.dumps(demo.events)


@pytest.mark.parametrize("key", [None, "invalid"])
def test_enabled_demo_requires_separate_encryption_key(key):
    with pytest.raises(ValidationError, match="RECORDER_DEMO_TRACE_ENCRYPTION_KEY"):
        Settings(_env_file=None, recorder_enabled=True, recorder_demo_trace_enabled=True,
                 recorder_demo_trace_encryption_key=key)


@pytest.mark.parametrize("output,valid", [
    (json.dumps({"recordable": False, "category": None, "confidence": 0.9, "summary": None}), True),
    ("not JSON", False),
])
def test_observer_contains_actual_llm_io_not_connection_secrets(monkeypatch, output, valid):
    import httpx
    requests = []

    def post(url, **kwargs):
        requests.append(kwargs["json"])
        return httpx.Response(200, json={"choices": [{"message": {"content": output}}]})

    monkeypatch.setattr("app.edge_audio.httpx.post", post)
    summarizer = OpenAICompatibleSummarizer(base_url="http://localhost:8001/v1",
        api_key="private-api-key", model="demo-model", allow_external=False, timeout_seconds=1)
    demo = DemoTrace()
    if valid:
        assert summarizer.summarize("接続確認です", demo_observer=demo.observe).recordable is False
    else:
        with pytest.raises(EdgeAudioError):
            summarizer.summarize("接続確認です", demo_observer=demo.observe)
    events = {event["kind"]: event["text"] for event in demo.events}
    assert events["llm_instruction"] == requests[0]["messages"][0]["content"]
    assert events["llm_input"] == requests[0]["messages"][1]["content"]
    assert events["llm_output"] == output
    assert "validation" in events
    assert "private-api-key" not in json.dumps(demo.events)
    assert "localhost" not in json.dumps(demo.events)
