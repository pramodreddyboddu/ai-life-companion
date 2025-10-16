"""Google OAuth endpoints."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
from google_auth_oauthlib.flow import Flow
from sqlalchemy.orm import Session

from app.api.deps import get_db_session, require_api_key
from app.db.models import ApiKey, User
from app.security.encryption import decrypt_value, encrypt_value, EncryptionError
from app.services.calendar_service import SCOPES
from app.settings import settings

router = APIRouter(prefix="/oauth/google", tags=["oauth"])

GOOGLE_AUTH_URI = "https://accounts.google.com/o/oauth2/auth"
GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"
DEFAULT_REDIRECT = "http://localhost:8000/oauth/google/callback"


def _build_flow(redirect_uri: str) -> Flow:
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(status_code=503, detail="Google OAuth is not configured.")

    client_config = {
        "web": {
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "auth_uri": GOOGLE_AUTH_URI,
            "token_uri": GOOGLE_TOKEN_URI,
        }
    }
    flow = Flow.from_client_config(client_config, scopes=SCOPES)
    flow.redirect_uri = redirect_uri
    return flow


def _resolve_redirect_uri() -> str:
    return settings.google_redirect_uri or DEFAULT_REDIRECT


@router.get("/start")
def start_google_oauth(
    api_key: ApiKey = Depends(require_api_key),
) -> RedirectResponse:
    redirect_uri = _resolve_redirect_uri()
    flow = _build_flow(redirect_uri)

    state_payload = json.dumps(
        {
            "user_id": str(api_key.user_id),
            "ts": datetime.now(timezone.utc).isoformat(),
        }
    )

    try:
        state_token = encrypt_value(state_payload)
    except EncryptionError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    authorization_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        state=state_token,
    )
    return RedirectResponse(url=authorization_url)


@router.get("/callback")
def oauth_callback(
    code: str,
    state: str,
    session: Session = Depends(get_db_session),
) -> HTMLResponse:
    try:
        state_payload = decrypt_value(state)
        data = json.loads(state_payload)
        user_id = uuid.UUID(data["user_id"])
    except (EncryptionError, ValueError, KeyError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail="Invalid OAuth state.") from exc

    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")

    redirect_uri = _resolve_redirect_uri()
    flow = _build_flow(redirect_uri)

    try:
        flow.fetch_token(code=code)
    except Exception as exc:  # pylint: disable=broad-except
        raise HTTPException(status_code=400, detail=f"Failed to fetch OAuth token: {exc}") from exc

    credentials = flow.credentials
    refresh_token = credentials.refresh_token or user.google_refresh_token
    if not refresh_token:
        raise HTTPException(status_code=400, detail="No refresh token received; ensure offline access is granted.")

    try:
        encrypted_token = encrypt_value(refresh_token)
    except EncryptionError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    user.google_refresh_token = encrypted_token
    session.add(user)
    session.commit()

    body = "<html><body><h2>Google Calendar connected successfully.</h2><p>You can close this tab.</p></body></html>"
    return HTMLResponse(content=body)
