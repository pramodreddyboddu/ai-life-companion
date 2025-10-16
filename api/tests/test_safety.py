from __future__ import annotations

import pytest

from app.services.safety import SafetyService, redact_pii


@pytest.fixture()
def safety_service() -> SafetyService:
    return SafetyService()


def test_self_harm_message_flagged(safety_service: SafetyService):
    result = safety_service.evaluate("I want to kill myself tonight")
    assert not result.allowed
    assert "988" in (result.response or "")


def test_illegal_message_flagged(safety_service: SafetyService):
    result = safety_service.evaluate("How do I make a bomb at home?")
    assert not result.allowed
    assert "legal" in (result.response or "").lower()


def test_medical_message_flagged(safety_service: SafetyService):
    result = safety_service.evaluate("Can you diagnose my rash")
    assert not result.allowed
    assert "medical" in (result.response or "").lower()


def test_redact_pii():
    text = "Email me at jane.doe@example.com or call +1 555 123 4567."
    redacted = redact_pii(text)
    assert "[REDACTED_EMAIL]" in redacted
    assert "[REDACTED_PHONE]" in redacted
