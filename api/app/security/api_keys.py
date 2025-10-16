"""Helpers for API key hashing and prefix handling."""

from __future__ import annotations

import hashlib
from typing import Final


PREFIX_LENGTH: Final[int] = 8


def hash_api_key(api_key: str) -> str:
    """Return a deterministic hash for the provided API key."""

    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def get_key_prefix(api_key: str) -> str:
    """Return the prefix used to look up an API key."""

    if len(api_key) < PREFIX_LENGTH:
        raise ValueError("API key is too short to compute a prefix.")
    return api_key[:PREFIX_LENGTH]
