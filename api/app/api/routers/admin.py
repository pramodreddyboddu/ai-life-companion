"""Admin observability endpoints."""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from redis import Redis
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db_session
from app.api.dependencies import get_feature_flag_service
from app.celery_app import celery_app
from app.db.models import FeatureFlag, Reminder
from app.services.feature_flags import FeatureFlagService
from app.settings import settings

router = APIRouter(prefix="/admin", tags=["admin"])


def require_admin_token(x_admin_token: str = Header(..., alias="X-Admin-Token")) -> None:
    expected = settings.admin_api_key
    if not expected or x_admin_token != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin token.")


def _redis_client() -> Redis:
    return Redis.from_url(settings.redis.url)


@router.get("/queues")
def get_queue_depth(_: None = Depends(require_admin_token)) -> Dict[str, Any]:
    client = _redis_client()
    depth = client.llen("celery")
    return {"queue": "celery", "depth": depth}


@router.get("/workers")
def get_worker_status(_: None = Depends(require_admin_token)) -> Dict[str, Any]:
    inspector = celery_app.control.inspect(timeout=2.0)
    ping = inspector.ping() if inspector else None
    if not ping:
        return {"status": "unreachable", "details": None}
    return {"status": "ok", "details": ping}


@router.get("/reminders")
def recent_reminders(
    session: Session = Depends(get_db_session),
    _: None = Depends(require_admin_token),
) -> List[Dict[str, Any]]:
    stmt = select(Reminder).order_by(Reminder.utc_ts.desc()).limit(100)
    reminders = session.execute(stmt).scalars().all()
    results: List[Dict[str, Any]] = []
    for reminder in reminders:
        results.append(
            {
                "id": str(reminder.id),
                "user_id": str(reminder.user_id),
                "text": reminder.text,
                "status": reminder.status.value,
                "utc_ts": reminder.utc_ts.isoformat() if reminder.utc_ts else None,
                "sent_at": reminder.sent_at.isoformat() if reminder.sent_at else None,
                "calendar_event_id": reminder.calendar_event_id,
            }
        )
    return results


class FeatureFlagPayload(BaseModel):
    key: str
    enabled: bool
    description: str | None = None


@router.get("/features")
def list_feature_flags(
    session: Session = Depends(get_db_session),
    _: None = Depends(require_admin_token),
    feature_flags: FeatureFlagService = Depends(get_feature_flag_service),
) -> List[Dict[str, Any]]:
    return feature_flags.describe_flags(session)


@router.post("/features")
def set_feature_flag(
    payload: FeatureFlagPayload,
    session: Session = Depends(get_db_session),
    _: None = Depends(require_admin_token),
    feature_flags: FeatureFlagService = Depends(get_feature_flag_service),
) -> Dict[str, Any]:
    record = feature_flags.set_flag(session, payload.key, payload.enabled, payload.description)
    return {
        "key": record.key,
        "enabled": bool(record.enabled),
        "description": record.description,
        "updated_at": record.updated_at.isoformat() if record.updated_at else None,
    }
