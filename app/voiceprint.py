"""Speaker-embedding helpers used only by the private GPU worker."""

from __future__ import annotations

import json
import math
from collections.abc import Sequence
from typing import Protocol


class VoiceprintError(RuntimeError):
    """Raised when a voiceprint cannot be safely produced or decoded."""


class VoiceprintExtractor(Protocol):
    model_name: str

    def extract(self, audio_path: str) -> list[float]: ...


def normalize_embedding(values: Sequence[float]) -> list[float]:
    embedding = [float(value) for value in values]
    if not embedding or not all(math.isfinite(value) for value in embedding):
        raise VoiceprintError("Speaker embedding is empty or contains invalid values")
    magnitude = math.sqrt(sum(value * value for value in embedding))
    if magnitude <= 0:
        raise VoiceprintError("Speaker embedding has zero magnitude")
    return [value / magnitude for value in embedding]


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right) or not left:
        raise VoiceprintError("Speaker embeddings have incompatible dimensions")
    normalized_left = normalize_embedding(left)
    normalized_right = normalize_embedding(right)
    return max(-1.0, min(1.0, sum(a * b for a, b in zip(normalized_left, normalized_right))))


def encrypt_embedding(values: Sequence[float], encryption_key: str) -> str:
    try:
        from cryptography.fernet import Fernet
    except ImportError as error:  # pragma: no cover - image configuration failure
        raise VoiceprintError("Voiceprint encryption support is unavailable") from error

    payload = json.dumps(
        normalize_embedding(values),
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
    ).encode("ascii")
    try:
        return Fernet(encryption_key.encode("ascii")).encrypt(payload).decode("ascii")
    except (ValueError, UnicodeError) as error:
        raise VoiceprintError("VOICEPRINT_ENCRYPTION_KEY is invalid") from error


def decrypt_embedding(encrypted_value: str, encryption_key: str) -> list[float]:
    try:
        from cryptography.fernet import Fernet, InvalidToken
    except ImportError as error:  # pragma: no cover - image configuration failure
        raise VoiceprintError("Voiceprint encryption support is unavailable") from error

    try:
        payload = Fernet(encryption_key.encode("ascii")).decrypt(encrypted_value.encode("ascii"))
        decoded = json.loads(payload)
    except (InvalidToken, ValueError, UnicodeError, json.JSONDecodeError) as error:
        raise VoiceprintError("Stored voiceprint cannot be decrypted") from error
    if not isinstance(decoded, list):
        raise VoiceprintError("Stored voiceprint has an invalid format")
    return normalize_embedding(decoded)


class PyannoteVoiceprintExtractor:
    """Load one pyannote embedding model lazily and extract whole-file vectors."""

    def __init__(self, *, model_name: str, token: str, device: str) -> None:
        self.model_name = model_name
        self.token = token
        self.device = device
        self._inference = None

    def _load_inference(self):
        if self._inference is not None:
            return self._inference
        try:
            import torch
            from pyannote.audio import Inference, Model
        except ImportError as error:  # pragma: no cover - GPU image configuration failure
            raise VoiceprintError("Speaker embedding dependencies are unavailable") from error
        try:
            model = Model.from_pretrained(self.model_name, token=self.token)
            if model is None:
                raise VoiceprintError("Speaker embedding model could not be loaded")
            inference = Inference(model, window="whole")
            inference.to(torch.device(self.device))
        except VoiceprintError:
            raise
        except Exception as error:
            raise VoiceprintError("Speaker embedding model could not be loaded") from error
        self._inference = inference
        return inference

    def extract(self, audio_path: str) -> list[float]:
        try:
            raw = self._load_inference()(audio_path)
            values = raw.tolist() if hasattr(raw, "tolist") else list(raw)
            while len(values) == 1 and isinstance(values[0], list):
                values = values[0]
            if any(isinstance(value, list) for value in values):
                raise VoiceprintError("Speaker embedding has an unexpected shape")
            return normalize_embedding(values)
        except VoiceprintError:
            raise
        except Exception as error:
            raise VoiceprintError("Speaker embedding extraction failed") from error
