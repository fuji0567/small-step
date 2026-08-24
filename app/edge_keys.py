"""Key generation and lookup helpers for kindergarten edge devices."""

from __future__ import annotations

from hashlib import sha256
from secrets import token_urlsafe


EDGE_KEY_PREFIX = "otayori_edge_"


def generate_edge_api_key() -> str:
    """Return a high-entropy credential shown only when created or rotated."""
    return f"{EDGE_KEY_PREFIX}{token_urlsafe(32)}"


def hash_edge_api_key(api_key: str) -> str:
    """Store a non-reversible lookup hash instead of an edge-device key."""
    return sha256(api_key.encode("utf-8")).hexdigest()
