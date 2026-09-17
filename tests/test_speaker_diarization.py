from pathlib import Path
import pytest
import sys
from types import SimpleNamespace

from app.speaker_diarization import (
    PyannoteCommunityDiarizer,
    SpeakerDiarizationError,
    build_quiet_speech_preprocess_command,
)


class FakeTurn:
    def __init__(self, start: float, end: float) -> None:
        self.start = start
        self.end = end


class FakePipeline:
    def __call__(self, audio):
        if audio["waveform"] == "quiet-speech-retry.wav":
            return [
                (FakeTurn(0.0, 4.0), "loud-voice"),
                (FakeTurn(4.2, 7.0), "quiet-voice"),
            ]
        return [(FakeTurn(0.0, 7.0), "only-detected-voice")]


def test_quiet_speech_preprocess_command_keeps_audio_local_and_mono(tmp_path):
    command = build_quiet_speech_preprocess_command(
        ffmpeg_bin="ffmpeg",
        audio_path=tmp_path / "source.wav",
        output_path=tmp_path / "retry.wav",
    )

    assert command[:8] == ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-i", str(tmp_path / "source.wav")]
    assert "acompressor" in command[command.index("-af") + 1]
    assert command[-7:] == [
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
        str(tmp_path / "retry.wav"),
    ]


def test_diarizer_uses_credible_quiet_speech_retry_without_retaining_audio(tmp_path, monkeypatch):
    source = tmp_path / "source.wav"
    source.write_bytes(b"original-audio")
    calls: list[tuple[Path, Path]] = []

    def fake_preprocessor(input_path: Path, output_path: Path) -> None:
        calls.append((input_path, output_path))
        output_path.write_bytes(input_path.read_bytes())

    diarizer = PyannoteCommunityDiarizer(
        model="test",
        token="token",
        device="cpu",
        preprocessor=fake_preprocessor,
    )
    diarizer._pipeline = FakePipeline()
    monkeypatch.setattr(diarizer, "_load_waveform", lambda path: (path.name, 16000))

    result = diarizer.diarize(source)

    assert result.speaker_count == 2
    assert result.used_low_volume_retry is True
    assert result.low_volume_retry_speaker_count == 2
    assert [segment.speaker_label for segment in result.segments] == ["speaker_01", "speaker_02"]
    assert calls[0][0] == source
    assert not calls[0][1].exists()


@pytest.mark.parametrize("suffix", [".mp4", ".aac", ".m4a", ".webm", ".wav"])
def test_diarizer_passes_preloaded_waveform_not_compressed_path(tmp_path, monkeypatch, suffix):
    source = tmp_path / ("source" + suffix)
    source.touch()
    waveform = object()
    seen = []
    diarizer = PyannoteCommunityDiarizer(
        model="test", token="token", device="cpu", low_volume_retry=False,
    )

    def pipeline(audio):
        assert "audio" not in audio
        assert audio == {"waveform": waveform, "sample_rate": 16000}
        seen.append(audio)
        return [(FakeTurn(0.0, 2.0), "voice")]

    monkeypatch.setattr(diarizer, "_load_waveform", lambda path: (waveform, 16000))
    diarizer._pipeline = pipeline
    assert diarizer.diarize(source).speaker_count == 1
    assert len(seen) == 1
    assert source.exists()
    assert not hasattr(diarizer, "_waveform")


def test_waveform_decode_failure_is_not_reported_as_success(tmp_path, monkeypatch):
    source = tmp_path / "broken.mp4"
    source.touch()
    diarizer = PyannoteCommunityDiarizer(model="test", token="token", device="cpu")
    diarizer._pipeline = lambda audio: pytest.fail("Must not analyze a failed decode")

    def decode(path):
        raise ValueError("Invalid audio")

    monkeypatch.setattr(diarizer, "_load_waveform", decode)
    with pytest.raises(SpeakerDiarizationError) as caught:
        diarizer.diarize(source)
    assert isinstance(caught.value.__cause__, ValueError)


@pytest.mark.parametrize("initial,cap,expected", [(32, 4, 4), (1, 4, 1), (8, 2, 2)])
def test_pipeline_caps_both_gpu_batches(monkeypatch, initial, cap, expected):
    pipeline = SimpleNamespace(embedding_batch_size=initial, segmentation_batch_size=initial)
    fake_api = SimpleNamespace(
        Pipeline=SimpleNamespace(from_pretrained=lambda *args, **kwargs: pipeline)
    )
    monkeypatch.setitem(sys.modules, "pyannote.audio", fake_api)
    diarizer = PyannoteCommunityDiarizer(
        model="test", token="token", device="cpu", batch_size=cap,
    )
    assert diarizer._load_pipeline() is pipeline
    assert pipeline.embedding_batch_size == expected
    assert pipeline.segmentation_batch_size == expected


@pytest.mark.parametrize("batch_size", [0, -1, 129])
def test_diarizer_rejects_invalid_batch_sizes(batch_size):
    with pytest.raises(ValueError):
        PyannoteCommunityDiarizer(model="test", token="token", device="cpu", batch_size=batch_size)


def test_audio_processor_uses_configured_batch_cap():
    from app.config import Settings
    from app.edge_audio import EdgeAudioProcessor

    processor = EdgeAudioProcessor(settings=Settings(
        _env_file=None, speaker_diarization_token="test", speaker_diarization_batch_size=2,
    ))
    assert processor.transcriber.diarizer.batch_size == 2
