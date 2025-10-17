"""Google Calendar endpoints."""

from __future__ import annotations

import os
import uuid
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_db_session, require_api_key
from app.api.dependencies import get_calendar_service, get_feature_flag_service
from app.db.models import ApiKey, Reminder, ReminderStatusEnum, User
from app.services.calendar_service import CalendarService
from app.services.feature_flags import FeatureFlagService

router = APIRouter(prefix="/calendar", tags=["calendar"])

DEFAULT_TZ = ZoneInfo(os.environ.get("TZ", "UTC"))


class CalendarAddRequest(BaseModel):
    reminder_id: uuid.UUID
    title: Optional[str] = Field(default=None, max_length=200)
    description: Optional[str] = Field(default=None, max_length=1000)
    duration_minutes: int = Field(default=60, ge=5, le=1440)


class CalendarAddResponse(BaseModel):
    status: str
    event_id: Optional[str] = None
    html_link: Optional[str] = None


@router.post("/add", response_model=CalendarAddResponse)
def add_calendar_event(
    payload: CalendarAddRequest,
    *,
    api_key: ApiKey = Depends(require_api_key),
    session: Session = Depends(get_db_session),
    calendar: CalendarService = Depends(get_calendar_service),
    feature_flags: FeatureFlagService = Depends(get_feature_flag_service),
    feature_flags: FeatureFlagService = Depends(get_feature_flag_service),
) -> CalendarAddResponse:
        if not feature_flags.is_enabled("calendar_integration", session=session):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Calendar integration disabled.")

    reminder = session.get(Reminder, payload.reminder_id)
    if reminder is None or reminder.user_id != api_key.user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reminder not found.")

    if reminder.status == ReminderStatusEnum.CANCELED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reminder has been canceled.")

    start_ts = reminder.utc_ts or reminder.run_ts
    if start_ts is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reminder does not have a schedule time.")

    title = payload.title or reminder.text
    description = payload.description
    end_ts = start_ts + timedelta(minutes=payload.duration_minutes)

        user = reminder.user or session.get(User, reminder.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    event = calendar.create_event(user, title=title, start_ts=start_ts, end_ts=end_ts, description=description)
    if event is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Calendar integration unavailable.")

    reminder.calendar_event_id = event.get("id")
    session.add(reminder)
    session.commit()

    return CalendarAddResponse(status="created", event_id=event.get("id"), html_link=event.get("htmlLink"))


@router.get("/list")
def list_calendar_events(
    *,
    date: Optional[str] = Query(default=None, description="ISO date (YYYY-MM-DD) in local timezone"),
    limit: int = Query(default=10, ge=1, le=50),
    api_key: ApiKey = Depends(require_api_key),
    session: Session = Depends(get_db_session),
    calendar: CalendarService = Depends(get_calendar_service),
    feature_flags: FeatureFlagService = Depends(get_feature_flag_service),
    feature_flags: FeatureFlagService = Depends(get_feature_flag_service),
) -> List[Dict[str, Any]]:
        if not feature_flags.is_enabled("calendar_integration", session=session):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Calendar integration disabled.")

    user = session.get(User, api_key.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

        target_date = _parse_date(date_str) if date_str else datetime.now(DEFAULT_TZ).date()
    start = datetime.combine(target_date, datetime.min.time(), tzinfo=DEFAULT_TZ)
    end = start + timedelta(days=1)

    events = calendar.list_events(user, start=start, end=end, limit=limit)
    return events


def _parse_date(value: str) -> datetime.date:
    try:
        return datetime.fromisoformat(value).date()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid date format.") from exc
