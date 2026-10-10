"""Check the installed decoder using synthetic audio without models or user data."""

from __future__ import annotations

import io
import math
import struct
import sys
import wave
from importlib.metadata import version


def synthetic_wav() -> io.BytesIO:
    sample_rate = 48000
    frames = bytearray()
    for index in range(sample_rate):
        sample = int(8192 * math.sin(2 * math.pi * 440 * index / sample_rate))
        frames.extend(struct.pack("<hh", sample, sample))
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as audio:
        audio.setnchannels(2)
        audio.setsampwidth(2)
        audio.setframerate(sample_rate)
        audio.writeframes(frames)
    buffer.seek(0)
    return buffer


def main() -> int:
    try:
        import numpy as np
        from faster_whisper.audio import decode_audio

        with synthetic_wav() as source:
            audio = decode_audio(source, sampling_rate=16000)
        if (
            audio.shape != (16000,)
            or audio.dtype != np.float32
            or not np.isfinite(audio).all()
            or not (np.abs(audio) > 0.1).any()
        ):
            print("音声デコード: 合成音声の検査に失敗", file=sys.stderr)
            return 1
        print("faster-whisper:", version("faster-whisper"))
        print("PyAV:", version("av"))
    except Exception:
        # Keep the same content-free failure policy as the recording worker.
        print("音声デコード: 失敗（依存ライブラリを確認してください）", file=sys.stderr)
        return 1
    print("音声デコード: 正常（合成音声のみ、モデル読み込みなし）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
