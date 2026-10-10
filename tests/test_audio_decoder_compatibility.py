from __future__ import annotations

import io
import shutil
import subprocess

import pytest

from scripts.check_audio_decoder import main, synthetic_wav


def test_decoder_smoke_check_uses_real_resampling(capsys):
    pytest.importorskip("faster_whisper.audio")

    assert main() == 0
    assert "音声デコード: 正常" in capsys.readouterr().out


def test_decoder_failure_does_not_expose_exception(capsys, monkeypatch):
    decoder = pytest.importorskip("faster_whisper.audio")

    def fail(*args, **kwargs):
        raise TypeError("private-child /private/audio.wav secret-key")

    monkeypatch.setattr(decoder, "decode_audio", fail)
    assert main() == 1
    output = capsys.readouterr()
    assert "音声デコード: 失敗" in output.err
    assert "private" not in output.out + output.err
    assert "secret-key" not in output.out + output.err


@pytest.mark.parametrize("audio_format, codec, flags", [
    ("webm", "libopus", []),
    ("mp4", "aac", ["-movflags", "frag_keyframe+empty_moov"]),
])
def test_browser_audio_formats_decode_without_a_model(audio_format, codec, flags):
    decoder = pytest.importorskip("faster_whisper.audio")
    np = pytest.importorskip("numpy")
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        pytest.skip("ffmpeg is required to synthesize browser audio")

    with synthetic_wav() as source:
        encoded = subprocess.run(
            [ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-i", "pipe:0",
             "-c:a", codec, *flags, "-f", audio_format, "pipe:1"],
            input=source.read(), capture_output=True, check=True, timeout=15,
        ).stdout
    with io.BytesIO(encoded) as source:
        audio = decoder.decode_audio(source, sampling_rate=16000)
    assert audio.ndim == 1
    assert 15000 <= audio.size <= 18000
    assert audio.dtype == np.float32
    assert np.isfinite(audio).all()
    assert (np.abs(audio) > 0.1).any()
