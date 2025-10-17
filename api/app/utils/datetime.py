from __future__ import annotations

from datetime import datetime, timedelta

from zoneinfo import ZoneInfo

import dateparser


LOCAL_TZ = ZoneInfo("America/Chicago")
UTC = ZoneInfo("UTC")


def parse_user_time_to_utc(text: str, now_local: datetime | None = None) -> datetime:
    now_local = now_local or datetime.now(LOCAL_TZ)

    dt = dateparser.parse(
        text,
        settings={
            "PREFER_DATES_FROM": "future",
            "RELATIVE_BASE": now_local.replace(tzinfo=None),
            "RETURN_AS_TIMEZONE_AWARE": False,
        },
    )
    if not dt:
        raise ValueError("Could not understand the time")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=LOCAL_TZ)
    else:
        dt = dt.astimezone(LOCAL_TZ)
    if dt < now_local:
        dt = dt + timedelta(days=1)
    return dt.astimezone(UTC)


__all__ = ["parse_user_time_to_utc", "LOCAL_TZ", "UTC"]
