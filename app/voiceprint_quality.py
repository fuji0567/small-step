"""Private, in-memory quality checks for voiceprint enrollment samples."""

from __future__ import annotations

from array import array
from dataclasses import dataclass
import math
from pathlib import Path
import subprocess
import sys
from typing import Callable, Protocol, Sequence

from app.models import VoiceprintQualityIssue
from app.speaker_diarization import SpeakerDiarizationResult, SpeakerDiarizer


VOICEPRINT_PCM_SAMPLE_RATE = 16_000
# Allow a small codec/timer margin around the requested 10-15 second recording.
MIN_SAMPLE_DURATION_SECONDS = 9.5
MAX_SAMPLE_DURATION_SECONDS = 16.0
MIN_SPEECH_SECONDS = 8.0
MIN_SPEECH_DBFS = -38.0
MIN_SIGNAL_TO_NOISE_DB = 8.0
MAX_CLIPPING_RATIO = 0.005
MIN_NOISE_MEASUREMENT_SECONDS = 0.5


@dataclass(frozen=True)
class VoiceprintSampleQuality:
    issue: VoiceprintQualityIssue | None
    duration_seconds: float
    speech_seconds: float
    speaker_count: int
    clipping_ratio: float
    speech_dbfs: float
    signal_to_noise_db: float | None


class VoiceprintQualityAnalyzer(Protocol):
    def analyze(self, audio_path: Path) -> VoiceprintSampleQuality: ...


def _merged_sample_ranges(
    diarization: SpeakerDiarizationResult,
    *,
    sample_rate: int,
    sample_count: int,
) -> list[tuple[int, int]]:
    ranges = sorted(
        (
            max(0, min(sample_count, round(segment.start_seconds * sample_rate))),
            max(0, min(sample_count, round(segment.end_seconds * sample_rate))),
        )
        for segment in diarization.segments
    )
    merged: list[tuple[int, int]] = []
    for start, end in ranges:
        if end <= start:
            continue
        if not merged or start > merged[-1][1]:
            merged.append((start, end))
            continue
        previous_start, previous_end = merged[-1]
        merged[-1] = (previous_start, max(previous_end, end))
    return merged


def _dbfs(root_mean_square: float) -> float:
    if root_mean_square <= 0:
        return float("-inf")
    return 20.0 * math.log10(root_mean_square / 32_768.0)


def evaluate_voiceprint_sample(
    samples: Sequence[int],
    *,
    sample_rate: int,
    diarization: SpeakerDiarizationResult,
) -> VoiceprintSampleQuality:
    """Evaluate decoded audio without retaining its waveform or speaker intervals."""

    if sample_rate <= 0 or not samples:
        return VoiceprintSampleQuality(
            issue=VoiceprintQualityIssue.invalid_audio,
            duration_seconds=0.0,
            speech_seconds=0.0,
            speaker_count=diarization.speaker_count,
            clipping_ratio=0.0,
            speech_dbfs=float("-inf"),
            signal_to_noise_db=None,
        )

    duration_seconds = len(samples) / sample_rate
    speech_ranges = _merged_sample_ranges(
        diarization,
        sample_rate=sample_rate,
        sample_count=len(samples),
    )
    speech_sample_count = sum(end - start for start, end in speech_ranges)
    speech_seconds = speech_sample_count / sample_rate
    speech_square_sum = sum(int(value) * int(value) for start, end in speech_ranges for value in samples[start:end])
    total_square_sum = sum(int(value) * int(value) for value in samples)
    noise_sample_count = len(samples) - speech_sample_count
    noise_square_sum = max(0, total_square_sum - speech_square_sum)
    speech_rms = math.sqrt(speech_square_sum / speech_sample_count) if speech_sample_count else 0.0
    noise_rms = math.sqrt(noise_square_sum / noise_sample_count) if noise_sample_count else 0.0
    speech_dbfs = _dbfs(speech_rms)
    clipping_ratio = sum(abs(int(value)) >= 32_700 for value in samples) / len(samples)
    signal_to_noise_db = None
    if noise_sample_count >= sample_rate * MIN_NOISE_MEASUREMENT_SECONDS:
        signal_to_noise_db = float("inf") if noise_rms <= 0 else 20.0 * math.log10(max(speech_rms, 1.0) / noise_rms)

    issue = None
    if duration_seconds < MIN_SAMPLE_DURATION_SECONDS:
        issue = VoiceprintQualityIssue.too_short
    elif duration_seconds > MAX_SAMPLE_DURATION_SECONDS:
        issue = VoiceprintQualityIssue.too_long
    elif diarization.speaker_count > 1:
        issue = VoiceprintQualityIssue.multiple_speakers
    elif diarization.speaker_count != 1 or speech_seconds < MIN_SPEECH_SECONDS:
        issue = VoiceprintQualityIssue.too_short
    elif clipping_ratio > MAX_CLIPPING_RATIO:
        issue = VoiceprintQualityIssue.clipping
    elif speech_dbfs < MIN_SPEECH_DBFS:
        issue = VoiceprintQualityIssue.too_quiet
    elif signal_to_noise_db is not None and signal_to_noise_db < MIN_SIGNAL_TO_NOISE_DB:
        issue = VoiceprintQualityIssue.too_noisy

    return VoiceprintSampleQuality(
        issue=issue,
        duration_seconds=duration_seconds,
        speech_seconds=speech_seconds,
        speaker_count=diarization.speaker_count,
        clipping_ratio=clipping_ratio,
        speech_dbfs=speech_dbfs,
        signal_to_noise_db=signal_to_noise_db,
    )


class LocalVoiceprintQualityAnalyzer:
    """Decode and inspect one sample locally without creating persistent artifacts."""

    def __init__(
        self,
        *,
        diarizer: SpeakerDiarizer,
        ffmpeg_bin: str = "ffmpeg",
        run_command: Callable[..., subprocess.CompletedProcess[bytes]] = subprocess.run,
    ) -> None:
        self.diarizer = diarizer
        self.ffmpeg_bin = ffmpeg_bin
        self.run_command = run_command

    def analyze(self, audio_path: Path) -> VoiceprintSampleQuality:
        if not audio_path.is_file():
            raise RuntimeError("Voiceprint sample was not found")
        try:
            completed = self.run_command(
                [
                    self.ffmpeg_bin,
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-nostdin",
                    "-i",
                    str(audio_path),
                    "-ac",
                    "1",
                    "-ar",
                    str(VOICEPRINT_PCM_SAMPLE_RATE),
                    "-f",
                    "s16le",
                    "pipe:1",
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            samples = array("h")
            samples.frombytes(completed.stdout)
            if sys.byteorder != "little":
                samples.byteswap()
            diarization = self.diarizer.diarize(audio_path)
        except (subprocess.CalledProcessError, ValueError):
            return VoiceprintSampleQuality(
                issue=VoiceprintQualityIssue.invalid_audio,
                duration_seconds=0.0,
                speech_seconds=0.0,
                speaker_count=0,
                clipping_ratio=0.0,
                speech_dbfs=float("-inf"),
                signal_to_noise_db=None,
            )
        except (OSError, subprocess.SubprocessError) as error:
            raise RuntimeError("Voiceprint sample could not be inspected") from error
        return evaluate_voiceprint_sample(
            samples,
            sample_rate=VOICEPRINT_PCM_SAMPLE_RATE,
            diarization=diarization,
        )
