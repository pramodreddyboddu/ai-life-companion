"""Reminder management endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db_session, require_api_key
from app.db.models import ApiKey, Reminder, ReminderStatusEnum

router = APIRouter(prefix="/reminders", tags=["reminders"])


@router.post("/{reminder_id}/cancel")
def cancel_reminder(
    reminder_id: uuid.UUID,
    *,
    api_key: ApiKey = Depends(require_api_key),
    session: Session = Depends(get_db_session),
) -> dict[str, Optional[str]]:
    """Cancel a scheduled reminder."""

    reminder = session.get(Reminder, reminder_id)
    if reminder is None or reminder.user_id != api_key.user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reminder not found.")

    if reminder.status == ReminderStatusEnum.CANCELED:
        return {"status": "noop", "message": "Reminder already canceled."}

    if reminder.status == ReminderStatusEnum.SENT:
        return {"status": "noop", "message": "Reminder already sent."}

    if reminder.status == ReminderStatusEnum.ERROR:
        return {"status": "noop", "message": "Reminder already marked as error."}

    reminder.status = ReminderStatusEnum.CANCELED
    session.add(reminder)
    session.commit()

    return {"status": "canceled"}
class ReminderResponse(BaseModel):
    id: uuid.UUID
    text: str
    status: ReminderStatusEnum
    run_ts: Optional[datetime]
    local_ts: Optional[datetime]
    utc_ts: Optional[datetime]
    sent_at: Optional[datetime]
    calendar_event_id: Optional[str]

    model_config = {"from_attributes": True}


@router.get("", response_model=List[ReminderResponse])
def list_reminders(
    *,
    api_key: ApiKey = Depends(require_api_key),
    session: Session = Depends(get_db_session),
) -> List[Reminder]:
    stmt = (
        select(Reminder)
        .where(Reminder.user_id == api_key.user_id)
        .order_by(Reminder.utc_ts.desc())
    )
    reminders = session.execute(stmt).scalars().all()
    return reminders
