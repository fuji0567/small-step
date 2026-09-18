"""Opt-in, encrypted, short-lived demo artifacts; never database or log content."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import UUID

from cryptography.fernet import Fernet, InvalidToken


TRACE_TTL = 300
GRANT_TTL = 86400
MAX_TRACE_BYTES = 262144
MAX_EVENTS = 40
MAX_TEXT = 8000


def demo_directory(session_dir: str | Path) -> Path:
    return Path(session_dir).resolve().parent / "recorder-demo-traces"


def cleanup_demo_files(session_dir: str | Path, *, now: float | None = None) -> None:
    directory = demo_directory(session_dir)
    if not directory.exists():
        return
    current = time.time() if now is None else now
    for path in directory.iterdir():
        ttl = GRANT_TTL if path.suffix == ".grant" else TRACE_TTL
        if path.is_symlink() or path.lstat().st_mtime + ttl <= current:
            path.unlink(missing_ok=True)


class DemoTrace:
    """A bounded per-call observer, not shared model state or internal reasoning."""

    def __init__(self) -> None:
        self.events: list[dict] = []
        self.truncated = False
        self.phase = "音声区間"

    def observe(self, kind: str, value: object) -> None:
        if len(self.events) >= MAX_EVENTS:
            self.truncated = True
            return
        text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
        clipped = len(text) > MAX_TEXT
        self.truncated |= clipped
        event = {"phase": self.phase, "kind": kind, "text": text[:MAX_TEXT], "truncated": clipped}
        if len(json.dumps([*self.events, event], ensure_ascii=False).encode()) > MAX_TRACE_BYTES - 16384:
            self.truncated = True
            return
        self.events.append(event)

    def clear(self) -> None:
        self.events.clear()


class RecorderDemoStorage:
    def __init__(self, session_dir: str | Path, key: str) -> None:
        self.directory = demo_directory(session_dir)
        self.cipher = Fernet(key.encode())

    def _path(self, session_id: str, suffix: str) -> Path:
        return self.directory / f"{UUID(session_id)}.{suffix}"

    def grant(self, session_id: str) -> None:
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.directory, 0o700)
        path = self._path(session_id, "grant")
        try:
            with path.open("xb") as stream:
                os.chmod(path, 0o600)
                stream.write(self.cipher.encrypt(session_id.encode()))
        except FileExistsError:
            pass

    def requested(self, session_id: str) -> bool:
        path = self._path(session_id, "grant")
        try:
            if path.is_symlink() or path.stat().st_size > 512:
                return False
            return self.cipher.decrypt(path.read_bytes(), ttl=GRANT_TTL).decode() == session_id
        except (OSError, InvalidToken, UnicodeError):
            return False

    def publish(self, session_id: str, trace: DemoTrace, *, outcome: str, record_id: str | None) -> None:
        if not self.requested(session_id):
            return
        created = time.time()
        data = json.dumps({
            "session_id": session_id, "expires_at": created + TRACE_TTL,
            "outcome": outcome, "record_id": record_id,
            "events": trace.events, "truncated": trace.truncated,
        }, ensure_ascii=False).encode()
        if len(data) > MAX_TRACE_BYTES:
            return
        # Bound disk use even during long continuous demonstrations.
        traces = sorted(self.directory.glob("*.trace"), key=lambda path: path.lstat().st_mtime)
        for path in traces[:-31]:
            path.unlink(missing_ok=True)
        with NamedTemporaryFile(dir=self.directory, prefix="demo-", delete=False) as stream:
            temporary = Path(stream.name)
            try:
                stream.write(self.cipher.encrypt(data))
                stream.flush()
                os.fsync(stream.fileno())
                os.replace(temporary, self._path(session_id, "trace"))
            finally:
                temporary.unlink(missing_ok=True)
        self._path(session_id, "grant").unlink(missing_ok=True)

    def read(self, session_id: str) -> dict | None:
        path = self._path(session_id, "trace")
        try:
            if path.is_symlink() or path.stat().st_size > MAX_TRACE_BYTES * 2:
                return None
            data = json.loads(self.cipher.decrypt(path.read_bytes(), ttl=TRACE_TTL))
            if data["session_id"] != session_id or data["expires_at"] <= time.time():
                self.erase(session_id)
                return None
            return data
        except (OSError, InvalidToken, ValueError, KeyError, TypeError):
            path.unlink(missing_ok=True)
            return None

    def erase(self, session_id: str) -> None:
        for suffix in ("trace", "grant"):
            self._path(session_id, suffix).unlink(missing_ok=True)
