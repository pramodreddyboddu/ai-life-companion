from __future__ import annotations

from datetime import datetime

import pytest
from zoneinfo import ZoneInfo

from app.utils.datetime import parse_user_time_to_utc


def test_parse_user_time_future_rollover():
    now = datetime(2025, 10, 16, 14, 50, tzinfo=ZoneInfo("America/Chicago"))
    dt = parse_user_time_to_utc("3pm", now_local=now)
    local_dt = dt.astimezone(ZoneInfo("America/Chicago"))
    assert local_dt.hour == 15
    assert local_dt.date() == now.date()
    assert dt > now


def test_parse_user_time_reject_past_year():
    now = datetime(2025, 10, 16, 14, 50, tzinfo=ZoneInfo("America/Chicago"))
    with pytest.raises(ValueError):
        parse_user_time_to_utc("October 10, 2023 9am", now_local=now)
