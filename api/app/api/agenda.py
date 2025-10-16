"""Agenda API endpoints."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db_session, require_api_key
from app.api.dependencies import get_calendar_service
from app.db.models import ApiKey, PlanEnum, Task, User
from app.services.calendar_service import CalendarService

router = APIRouter(prefix="/agenda", tags=["agenda"])


def _parse_query_timestamp(value: Optional[str], *, default: datetime) -> datetime:
    if not value:
        return default
    candidate = value.strip()
    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"
    try:
        result = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid datetime format.") from exc
    if result.tzinfo is None:
        result = result.replace(tzinfo=timezone.utc)
    return result.astimezone(timezone.utc)


@router.get("")
def get_agenda(
    *,
    api_key: ApiKey = Depends(require_api_key),
    session: Session = Depends(get_db_session),
    calendar_service: CalendarService = Depends(get_calendar_service),
    start: Optional[str] = Query(None, alias="from"),
    end: Optional[str] = Query(None, alias="to"),
) -> dict:
    user = session.get(User, api_key.user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    if user.plan != PlanEnum.PRO:
        raise HTTPException(status_code=402, detail="Upgrade to Pro to access the agenda.")

    now = datetime.now(timezone.utc)
    start_dt = _parse_query_timestamp(start, default=now)
    end_dt = _parse_query_timestamp(end, default=start_dt + timedelta(days=7))
    if end_dt < start_dt:
        end_dt = start_dt + timedelta(days=1)

    events = calendar_service.list_events(user, start=start_dt, end=end_dt, limit=5)

    task_query = (
        select(Task)
        .where(Task.user_id == user.id)
        .where(Task.due_ts.is_not(None))
        .where(Task.due_ts >= start_dt)
        .where(Task.due_ts <= end_dt)
        .order_by(Task.due_ts.asc())
        .limit(5)
    )
    tasks = session.execute(task_query).scalars().all()

    return {
        "events": events,
        "tasks": [
            {
                "id": str(task.id),
                "title": task.title,
                "due_ts": task.due_ts.isoformat() if task.due_ts else None,
                "calendar_event_id": task.linked_calendar_event_id,
            }
            for task in tasks
        ],
        "window": {"from": start_dt.isoformat(), "to": end_dt.isoformat()},
    }
