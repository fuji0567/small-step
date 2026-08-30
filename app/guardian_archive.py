"""Opaque, short-lived access tokens for a guardian's delivery archive."""

from __future__ import annotations

from hashlib import sha256
from secrets import token_urlsafe


GUARDIAN_ARCHIVE_TOKEN_PREFIX = "ssa_"


def generate_guardian_archive_token() -> str:
    """Return a high-entropy secret suitable for a one-child archive link."""

    return f"{GUARDIAN_ARCHIVE_TOKEN_PREFIX}{token_urlsafe(32)}"


def hash_guardian_archive_token(token: str) -> str:
    """Store only a non-reversible lookup hash, never the usable URL secret."""

    return sha256(token.encode("utf-8")).hexdigest()
