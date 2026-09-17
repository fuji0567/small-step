"""Local, anonymous speaker diarization for edge audio files.

The diarizer labels voices only as temporary speaker_01-style identifiers. It
does not identify people, store voiceprints, or send raw audio to the API.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
from typing import Callable, Protocol

from pydantic import BaseModel, Field, model_validator


# Keep soft, distant speech audible without turning silence into excessive gain.
QUIET_SPEECH_AUDIO_FILTER = (
    "highpass=f=80,"
    "acompressor=threshold=0.1:ratio=4:attack=20:release=250:makeup=8,"
    "dynaudnorm=f=100:g=15:p=0.9:m=15"
)
MIN_RETRY_SPEAKER_SECONDS = 1.5


class SpeakerDiarizationError(RuntimeError):
    """Raised when local diarization is unavailable or unsafe to run."""


class SpeakerSegment(BaseModel):
    """One anonymous local speech interval."""

    speaker_label: str = Field(pattern=r"^speaker_\d{2}$")
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(gt=0)

    @model_validator(mode="after")
    def validate_duration(self) -> "SpeakerSegment":
        if self.end_seconds <= self.start_seconds:
            raise ValueError("end_seconds must be greater than start_seconds")
        return self


class SpeakerDiarizationResult(BaseModel):
    """Anonymous diarization result that stays on the edge device."""

    speaker_count: int = Field(ge=0)
    segments: list[SpeakerSegment]
    used_low_volume_retry: bool = False
    low_volume_retry_speaker_count: int | None = Field(default=None, ge=0)


class SpeakerDiarizer(Protocol):
    def diarize(self, audio_path: Path) -> SpeakerDiarizationResult:
        """Separate locally stored audio into anonymous speaker intervals."""


def build_anonymous_diarization_result(
    turns: Iterable[tuple[float, float, str]],
) -> SpeakerDiarizationResult:
    """Replace provider-specific labels with ordered anonymous labels."""

    label_map: dict[str, str] = {}
    segments: list[SpeakerSegment] = []
    for start_seconds, end_seconds, provider_label in sorted(turns, key=lambda turn: (turn[0], turn[1], turn[2])):
        anonymous_label = label_map.setdefault(provider_label, f"speaker_{len(label_map) + 1:02d}")
        segments.append(
            SpeakerSegment(
                speaker_label=anonymous_label,
                start_seconds=start_seconds,
                end_seconds=end_seconds,
            )
        )
    return SpeakerDiarizationResult(speaker_count=len(label_map), segments=segments)


def build_quiet_speech_preprocess_command(
    *,
    ffmpeg_bin: str,
    audio_path: Path,
    output_path: Path,
) -> list[str]:
    """Build a local-only gain balancing command for a retry attempt."""

    return [
        ffmpeg_bin,
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-y",
        "-i",
        str(audio_path),
        "-af",
        QUIET_SPEECH_AUDIO_FILTER,
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
        str(output_path),
    ]


def preprocess_quiet_speech(
    *,
    ffmpeg_bin: str,
    audio_path: Path,
    output_path: Path,
    run_command: Callable[..., object] = subprocess.run,
) -> None:
    """Create one temporary balanced WAV without modifying the source audio."""

    command = build_quiet_speech_preprocess_command(
        ffmpeg_bin=ffmpeg_bin,
        audio_path=audio_path,
        output_path=output_path,
    )
    try:
        run_command(command, check=True)
    except (OSError, subprocess.SubprocessError) as error:
        raise SpeakerDiarizationError("Could not prepare the low-volume speaker retry") from error
    if not output_path.is_file() or output_path.stat().st_size == 0:
        raise SpeakerDiarizationError("Low-volume speaker retry did not create an audio file")


def should_use_low_volume_retry_result(
    *,
    original: SpeakerDiarizationResult,
    retry: SpeakerDiarizationResult,
) -> bool:
    """Reject short false splits caused by background noise after gain balancing."""

    if retry.speaker_count <= original.speaker_count:
        return False

    durations: dict[str, float] = defaultdict(float)
    for segment in retry.segments:
        durations[segment.speaker_label] += segment.end_seconds - segment.start_seconds
    return bool(durations) and min(durations.values()) >= MIN_RETRY_SPEAKER_SECONDS


class PyannoteCommunityDiarizer:
    """Lazy local adapter for the pyannote Community-1 offline pipeline."""

    def __init__(
        self,
        *,
        model: str,
        token: str | None,
        device: str,
        low_volume_retry: bool = True,
        ffmpeg_bin: str = "ffmpeg",
        preprocessor: Callable[[Path, Path], None] | None = None,
    ) -> None:
        self.model = model
        self.token = token
        self.device = device
        self.low_volume_retry = low_volume_retry
        self.ffmpeg_bin = ffmpeg_bin
        self.preprocessor = preprocessor
        self._pipeline: object | None = None

    def _load_pipeline(self) -> object:
        if not self.token:
            raise SpeakerDiarizationError(
                "SPEAKER_DIARIZATION_TOKEN must be configured before speaker diarization"
            )
        try:
            from pyannote.audio import Pipeline
        except ImportError as error:
            raise SpeakerDiarizationError(
                "pyannote.audio is not installed. Install with: pip install -e '.[speaker-diarization]'"
            ) from error

        pipeline = Pipeline.from_pretrained(self.model, token=self.token)
        if pipeline is None:
            raise SpeakerDiarizationError("Could not load the local speaker diarization pipeline")
        if self.device != "cpu":
            try:
                import torch

                pipeline.to(torch.device(self.device))
            except (ImportError, RuntimeError) as error:
                raise SpeakerDiarizationError(
                    f"Could not move the speaker diarization pipeline to {self.device}"
                ) from error
        return pipeline

    def _load_waveform(self, audio_path: Path) -> tuple[object, int]:
        from pyannote.audio.core.io import Audio

        return Audio(sample_rate=16000, mono="downmix")(str(audio_path))

    def _diarize_once(self, audio_path: Path) -> SpeakerDiarizationResult:
        waveform = None
        try:
            if self._pipeline is None:
                self._pipeline = self._load_pipeline()
            # Decode once: compressed-file range seeks can return a different
            # sample count than pyannote's crop expects. Crop the waveform instead.
            waveform, sample_rate = self._load_waveform(audio_path)
            output = self._pipeline({"waveform": waveform, "sample_rate": sample_rate})
            diarization = getattr(output, "exclusive_speaker_diarization", None)
            if diarization is None:
                diarization = getattr(output, "speaker_diarization", output)
            if hasattr(diarization, "itertracks"):
                turns = (
                    (float(turn.start), float(turn.end), str(label))
                    for turn, _track, label in diarization.itertracks(yield_label=True)
                )
            else:
                turns = (
                    (float(turn.start), float(turn.end), str(label))
                    for turn, label in diarization
                )
            return build_anonymous_diarization_result(turns)
        except SpeakerDiarizationError:
            raise
        except Exception as error:
            raise SpeakerDiarizationError("Local speaker diarization failed") from error
        finally:
            waveform = None

    def _preprocess_quiet_speech(self, audio_path: Path, output_path: Path) -> None:
        if self.preprocessor is not None:
            self.preprocessor(audio_path, output_path)
            return
        preprocess_quiet_speech(
            ffmpeg_bin=self.ffmpeg_bin,
            audio_path=audio_path,
            output_path=output_path,
        )

    def diarize(self, audio_path: Path) -> SpeakerDiarizationResult:
        if not audio_path.is_file():
            raise SpeakerDiarizationError("Audio file was not found")

        original_result = self._diarize_once(audio_path)
        if not self.low_volume_retry or original_result.speaker_count != 1:
            return original_result

        # The enhanced recording stays in a temporary directory and is removed immediately.
        try:
            with TemporaryDirectory(prefix="small-step-diarization-") as directory:
                retry_audio_path = Path(directory) / "quiet-speech-retry.wav"
                self._preprocess_quiet_speech(audio_path, retry_audio_path)
                retry_result = self._diarize_once(retry_audio_path)
        except SpeakerDiarizationError:
            return original_result

        if should_use_low_volume_retry_result(original=original_result, retry=retry_result):
            return retry_result.model_copy(
                update={
                    "used_low_volume_retry": True,
                    "low_volume_retry_speaker_count": retry_result.speaker_count,
                }
            )
        return original_result.model_copy(
            update={"low_volume_retry_speaker_count": retry_result.speaker_count}
        )
