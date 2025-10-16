"""User-related API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db_session, require_api_key
from app.db.models import ApiKey, User

router = APIRouter(prefix="/users", tags=["users"])


class PushTokenPayload(BaseModel):
    push_token: str | None


@router.post("/push-token")
def update_push_token(
    payload: PushTokenPayload,
    *,
    api_key: ApiKey = Depends(require_api_key),
    session: Session = Depends(get_db_session),
) -> dict:
    user = session.get(User, api_key.user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")

    user.push_token = payload.push_token
    session.add(user)
    session.commit()

    return {"status": "ok"}
