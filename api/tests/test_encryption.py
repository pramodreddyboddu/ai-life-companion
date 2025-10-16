from __future__ import annotations

from app.security import encryption
from cryptography.fernet import Fernet
from app.settings import settings


def test_encrypt_decrypt_roundtrip(monkeypatch):
    key = Fernet.generate_key().decode("utf-8")
    monkeypatch.setattr(settings, "encryption_key", key)
    encryption._get_fernet.cache_clear()  # type: ignore[attr-defined]

    original = "sensitive-token"
    token = encryption.encrypt_value(original)
    assert token != original
    decrypted = encryption.decrypt_value(token)
    assert decrypted == original

    encryption._get_fernet.cache_clear()  # type: ignore[attr-defined]
