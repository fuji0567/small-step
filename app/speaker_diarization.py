"""Local, anonymous speaker diarization for edge audio files.

The diarizer labels voices only as temporary speaker_01-style identifiers. It
does not identify people, store voiceprints, or send raw audio to the API.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, Field, model_validator


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


class PyannoteCommunityDiarizer:
    """Lazy local adapter for the pyannote Community-1 offline pipeline."""

    def __init__(self, *, model: str, token: str | None, device: str) -> None:
        self.model = model
        self.token = token
        self.device = device
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

    def diarize(self, audio_path: Path) -> SpeakerDiarizationResult:
        if not audio_path.is_file():
            raise SpeakerDiarizationError("Audio file was not found")
        if self._pipeline is None:
            self._pipeline = self._load_pipeline()

        try:
            output = self._pipeline(str(audio_path))
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
