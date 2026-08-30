"""Private, short-lived storage for cloud GPU audio jobs.

The database receives metadata only. Audio bytes are written under a random
server-side key and never retain the filename supplied by a recording device.
"""

from pathlib import Path
from uuid import UUID

from fastapi import UploadFile

from app.edge_audio import SUPPORTED_AUDIO_SUFFIXES


class CloudAudioStorageError(RuntimeError):
    """Raised when an uploaded audio file cannot be safely stored."""


class CloudAudioJobStorage:
    def __init__(self, *, job_dir: str, max_file_bytes: int) -> None:
        self.job_dir = Path(job_dir).expanduser().resolve()
        self.max_file_bytes = max_file_bytes

    def ensure_directory(self) -> None:
        self.job_dir.mkdir(parents=True, exist_ok=True)
        if not self.job_dir.is_dir():
            raise CloudAudioStorageError("CLOUD_AUDIO_JOB_DIR must be a directory")

    def storage_key_for_upload(self, *, job_id: str, filename: str | None) -> str:
        suffix = Path(filename or "").suffix.lower()
        if suffix not in SUPPORTED_AUDIO_SUFFIXES:
            raise CloudAudioStorageError("Unsupported audio format")
        try:
            UUID(job_id)
        except ValueError as error:
            raise CloudAudioStorageError("Invalid cloud audio job ID") from error
        return f"{job_id}{suffix}"

    def path_for(self, storage_key: str) -> Path:
        candidate = (self.job_dir / storage_key).resolve()
        try:
            candidate.relative_to(self.job_dir)
        except ValueError as error:
            raise CloudAudioStorageError("Invalid cloud audio storage key") from error
        return candidate

    async def store_upload(self, *, upload: UploadFile, job_id: str) -> str:
        """Store a bounded upload atomically and return only its random storage key."""

        self.ensure_directory()
        storage_key = self.storage_key_for_upload(job_id=job_id, filename=upload.filename)
        destination = self.path_for(storage_key)
        temporary = self.path_for(f".{storage_key}.upload")
        total_size = 0
        try:
            with temporary.open("xb") as stream:
                while chunk := await upload.read(1_048_576):
                    total_size += len(chunk)
                    if total_size > self.max_file_bytes:
                        raise CloudAudioStorageError("Audio file exceeds EDGE_AUDIO_MAX_FILE_BYTES")
                    stream.write(chunk)
            if total_size == 0:
                raise CloudAudioStorageError("Audio file is empty")
            temporary.replace(destination)
            return storage_key
        except FileExistsError as error:
            raise CloudAudioStorageError("A cloud audio job already exists") from error
        finally:
            temporary.unlink(missing_ok=True)
            await upload.close()

    def delete(self, storage_key: str) -> None:
        self.path_for(storage_key).unlink(missing_ok=True)
