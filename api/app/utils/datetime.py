"""Datetime helpers for natural language scheduling."""

from __future__ import annotations

import re
from datetime import datetime, timedelta

import dateparser
from zoneinfo import ZoneInfo


LOCAL_TZ = ZoneInfo("America/Chicago")
UTC_TZ = ZoneInfo("UTC")


def parse_user_time_to_utc(text: str, now_local: datetime | None = None) -> datetime:
    """Parse user-entered time text into a future UTC datetime."""

    now_local = now_local or datetime.now(LOCAL_TZ)

    parsed = dateparser.parse(
        text,
        settings={
            "PREFER_DATES_FROM": "future",
            "RELATIVE_BASE": now_local.replace(tzinfo=None),
        },
    )
    if parsed is None:
        raise ValueError("Could not understand the time expression.")

    explicit_year = bool(re.search(r"\b\d{4}\b", text))

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=LOCAL_TZ)
    else:
        parsed = parsed.astimezone(LOCAL_TZ)

    if parsed.year < now_local.year:
        if explicit_year:
            raise ValueError("Year is in the past.")
        parsed = parsed.replace(year=now_local.year)

    if parsed < now_local:
        parsed = parsed + timedelta(days=1)

    return parsed.astimezone(UTC_TZ)


__all__ = ["parse_user_time_to_utc", "LOCAL_TZ", "UTC_TZ"]

