"""Private storage helpers for the independent ``/rec/`` recorder.

The database stores only a random relative key and integrity metadata.  This
module intentionally does not inspect or retain the upload's original name.
Files are streamed to a temporary random name and atomically renamed only
after the size and SHA-256 checks pass.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import UploadFile


class RecorderStorageError(RuntimeError):
    """Raised when a recorder upload cannot be safely accepted or removed."""


_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")

# MediaRecorder implementations commonly append a codec parameter (for
# example ``audio/webm;codecs=opus``).  The base family is what is persisted.
SUPPORTED_MEDIA_TYPES: dict[str, str] = {
    "audio/mp4": ".mp4",
    "video/mp4": ".mp4",
    "audio/aac": ".aac",
    "audio/x-m4a": ".m4a",
    "audio/webm": ".webm",
    "video/webm": ".webm",
}


def normalise_media_type(media_type: str | None) -> str:
    """Return a supported, lower-case MIME base type."""

    value = (media_type or "").split(";", 1)[0].strip().lower()
    if value not in SUPPORTED_MEDIA_TYPES:
        raise RecorderStorageError("Unsupported recorder media type")
    return value


def validate_sha256(value: str) -> str:
    digest = value.strip().lower()
    if not _SHA256_RE.fullmatch(digest):
        raise RecorderStorageError("sha256 must be a 64-character hexadecimal digest")
    return digest


class RecorderStorage:
    """Bounded, path-safe, random-key storage for recorder session segments."""

    def __init__(self, *, session_dir: str, max_segment_bytes: int) -> None:
        self.session_dir = Path(session_dir).expanduser().resolve()
        self.max_segment_bytes = max_segment_bytes

    def ensure_directory(self) -> None:
        self.session_dir.mkdir(parents=True, exist_ok=True)
        if not self.session_dir.is_dir():
            raise RecorderStorageError("RECORDER_SESSION_DIR must be a directory")

    @staticmethod
    def _validate_session_id(session_id: str) -> str:
        try:
            return str(UUID(session_id))
        except (ValueError, AttributeError, TypeError) as error:
            raise RecorderStorageError("Invalid recorder session ID") from error

    def session_path(self, session_id: str) -> Path:
        safe_id = self._validate_session_id(session_id)
        candidate = (self.session_dir / safe_id).resolve()
        try:
            candidate.relative_to(self.session_dir)
        except ValueError as error:  # pragma: no cover - defensive path guard
            raise RecorderStorageError("Invalid recorder session path") from error
        return candidate

    def path_for(self, storage_key: str) -> Path:
        """Resolve a DB key below the root and reject traversal."""

        if not storage_key or "\\" in storage_key:
            raise RecorderStorageError("Invalid recorder storage key")
        candidate = (self.session_dir / storage_key).resolve()
        try:
            candidate.relative_to(self.session_dir)
        except ValueError as error:
            raise RecorderStorageError("Invalid recorder storage key") from error
        return candidate

    async def store_upload(
        self,
        *,
        upload: UploadFile,
        session_id: str,
        expected_sha256: str,
        media_type: str,
    ) -> tuple[str, int, str]:
        """Stream an upload and atomically store it under a random key.

        Returns ``(storage_key, size_bytes, computed_sha256)``.  The caller
        compares the computed digest to the client-provided digest before it
        changes the database.
        """

        safe_session_id = self._validate_session_id(session_id)
        expected = validate_sha256(expected_sha256)
        safe_media_type = normalise_media_type(media_type)
        self.ensure_directory()
        session_path = self.session_path(safe_session_id)
        session_path.mkdir(parents=True, exist_ok=True)

        extension = SUPPORTED_MEDIA_TYPES[safe_media_type]
        random_name = f"{uuid4().hex}{extension}"
        storage_key = f"{safe_session_id}/{random_name}"
        destination = self.path_for(storage_key)
        temporary = self.path_for(f"{safe_session_id}/.{uuid4().hex}.upload")
        total_size = 0
        digest = hashlib.sha256()
        try:
            with temporary.open("xb") as stream:
                while chunk := await upload.read(1_048_576):
                    total_size += len(chunk)
                    if total_size > self.max_segment_bytes:
                        raise RecorderStorageError("Recorder segment exceeds RECORDER_MAX_SEGMENT_BYTES")
                    digest.update(chunk)
                    stream.write(chunk)
                if total_size == 0:
                    raise RecorderStorageError("Recorder segment is empty")
                computed = digest.hexdigest()
                if computed != expected:
                    raise RecorderStorageError("sha256 does not match the uploaded bytes")
            # Path.replace is atomic on the same filesystem, and the filename
            # is freshly random so it cannot overwrite a previous segment.
            temporary.replace(destination)
            return storage_key, total_size, computed
        finally:
            temporary.unlink(missing_ok=True)
            await upload.close()

    def delete(self, storage_key: str) -> None:
        self.path_for(storage_key).unlink(missing_ok=True)

    def delete_session(self, session_id: str) -> None:
        """Delete one validated session directory and its files."""

        directory = self.session_path(session_id)
        if not directory.exists():
            return
        # The directory is always the UUID child directly below the configured
        # root, so this cleanup cannot traverse outside the recorder inbox.
        for child in directory.iterdir():
            if child.is_file() or child.is_symlink():
                child.unlink(missing_ok=True)
        try:
            directory.rmdir()
        except OSError:
            # A concurrent worker may have created a new file.  The request
            # still removed the files it owns; a later expiry pass can retry.
            pass
