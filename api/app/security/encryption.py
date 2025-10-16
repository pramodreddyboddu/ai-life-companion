"""Utilities for encrypting and decrypting sensitive values."""

from __future__ import annotations

from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.settings import settings


class EncryptionError(RuntimeError):
    """Raised when encryption configuration or operations fail."""


@lru_cache(maxsize=1)
def _get_fernet() -> Fernet:
    key = settings.encryption_key
    if not key:
        raise EncryptionError("ENCRYPTION_KEY is not configured.")
    try:
        return Fernet(key.encode("utf-8"))
    except (ValueError, TypeError) as exc:
        raise EncryptionError("Invalid ENCRYPTION_KEY format.") from exc


def encrypt_value(value: str) -> str:
    """Encrypt the provided string."""

    if value is None:
        raise EncryptionError("Cannot encrypt a null value.")
    token = _get_fernet().encrypt(value.encode("utf-8"))
    return token.decode("utf-8")


def decrypt_value(token: str) -> str:
    """Decrypt a previously encrypted string."""

    if not token:
        raise EncryptionError("Token is empty.")
    try:
        value = _get_fernet().decrypt(token.encode("utf-8"))
    except InvalidToken as exc:
        raise EncryptionError("Failed to decrypt value.") from exc
    return value.decode("utf-8")
