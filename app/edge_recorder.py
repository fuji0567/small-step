"""Local microphone recording helpers for the privacy-preserving edge pipeline."""

from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import subprocess
from uuid import uuid4


def build_record_command(
    *,
    ffmpeg_bin: str,
    audio_device: str,
    chunk_seconds: float,
    output_path: Path,
) -> list[str]:
    """Build an avfoundation command without invoking a shell."""

    return [
        ffmpeg_bin,
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-y",
        "-f",
        "avfoundation",
        "-i",
        audio_device,
        "-t",
        str(chunk_seconds),
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
        str(output_path),
    ]


def record_one_chunk(
    *,
    ffmpeg_bin: str,
    audio_device: str,
    chunk_seconds: float,
    inbox_dir: str,
    run_command=subprocess.run,
) -> Path:
    """Record one complete WAV file and expose it to the watcher atomically."""

    inbox = Path(inbox_dir).expanduser().resolve()
    inbox.mkdir(parents=True, exist_ok=True)
    recording_id = f"capture-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{uuid4().hex}"
    temporary_path = inbox / f".{recording_id}.partial.wav"
    completed_path = inbox / f"{recording_id}.wav"
    command = build_record_command(
        ffmpeg_bin=ffmpeg_bin,
        audio_device=audio_device,
        chunk_seconds=chunk_seconds,
        output_path=temporary_path,
    )
    try:
        run_command(command, check=True)
        if not temporary_path.is_file() or temporary_path.stat().st_size == 0:
            raise RuntimeError("ffmpeg did not create an audio file")
        os.replace(temporary_path, completed_path)
    except (OSError, subprocess.SubprocessError) as error:
        raise RuntimeError("マイク録音に失敗しました。入力デバイスとマイクの許可を確認してください。") from error
    finally:
        # This also removes incomplete raw audio if Control+C interrupts ffmpeg.
        temporary_path.unlink(missing_ok=True)
    return completed_path


def list_audio_devices(ffmpeg_bin: str) -> None:
    """Ask ffmpeg to show the Mac audio-device indexes for one-time setup."""

    subprocess.run(
        [ffmpeg_bin, "-hide_banner", "-f", "avfoundation", "-list_devices", "true", "-i", ""],
        check=False,
    )
