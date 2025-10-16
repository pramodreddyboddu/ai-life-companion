"""Safety and content filtering utilities for chat requests."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


SELF_HARM_KEYWORDS = [
    "end my life",
    "kill myself",
    "suicide",
    "self harm",
    "hurt myself",
]

ILLEGAL_KEYWORDS = [
    "buy a gun without",
    "make a bomb",
    "evade taxes",
    "hack into",
    "steal",
]

MEDICAL_FINANCIAL_KEYWORDS = [
    "diagnose",
    "prescribe",
    "medicine for",
    "medical advice",
    "investment advice",
    "financial advice",
    "buy stocks",
]


SELF_HARM_RESPONSE = (
    "I'm really sorry you're going through this, but I'm not able to help. "
    "If you're in immediate danger, please contact your local emergency services or a crisis hotline. "
    "In the U.S. you can call or text 988 for the Suicide & Crisis Lifeline."
)

ILLEGAL_RESPONSE = (
    "I can't help with that. If you have legal concerns, please reach out to a qualified legal professional."
)

MEDICAL_FINANCIAL_RESPONSE = (
    "I'm not able to provide medical or financial advice. "
    "Please consult with a licensed healthcare or financial professional who can help you."
)

EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
PHONE_PATTERN = re.compile(r"\+?\d[\d\-\s]{6,}\d")


@dataclass
class SafetyResult:
    allowed: bool
    response: Optional[str] = None
    reason: Optional[str] = None


class SafetyService:
    """Provide lightweight safety checks for chat input."""

    def evaluate(self, message: str) -> SafetyResult:
        lowered = message.lower()

        if any(keyword in lowered for keyword in SELF_HARM_KEYWORDS):
            return SafetyResult(allowed=False, response=SELF_HARM_RESPONSE, reason="self_harm")

        if any(keyword in lowered for keyword in ILLEGAL_KEYWORDS):
            return SafetyResult(allowed=False, response=ILLEGAL_RESPONSE, reason="illegal_activity")

        if any(keyword in lowered for keyword in MEDICAL_FINANCIAL_KEYWORDS):
            return SafetyResult(
                allowed=False,
                response=MEDICAL_FINANCIAL_RESPONSE,
                reason="restricted_advice",
            )

        return SafetyResult(allowed=True)


def redact_pii(value: str) -> str:
    """Redact email addresses and phone numbers from log messages."""

    if not value:
        return value

    redacted = EMAIL_PATTERN.sub("[REDACTED_EMAIL]", value)
    redacted = PHONE_PATTERN.sub("[REDACTED_PHONE]", redacted)
    return redacted


__all__ = ["SafetyService", "SafetyResult", "redact_pii"]
