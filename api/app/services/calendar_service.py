"""Google Calendar integration helpers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List, Optional

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from loguru import logger

from app.db.models import Task, User
from app.security.encryption import decrypt_value, EncryptionError
from app.settings import settings

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
TOKEN_URI = "https://oauth2.googleapis.com/token"


class CalendarService:
    """Encapsulates Google Calendar interactions."""

    def __init__(self) -> None:
        if not settings.google_client_id or not settings.google_client_secret:
            logger.warning("Google client configuration is incomplete; calendar features disabled.")

    def _build_credentials(self, user: User) -> Optional[Credentials]:
        if not settings.google_client_id or not settings.google_client_secret:
            return None
        if not user.google_refresh_token:
            return None

        try:
            refresh_token = decrypt_value(user.google_refresh_token)
        except EncryptionError as exc:
            logger.error("Unable to decrypt refresh token for user %s: %s", user.id, exc)
            return None

        credentials = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri=TOKEN_URI,
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
            scopes=SCOPES,
        )

        try:
            credentials.refresh(Request())
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("Failed to refresh Google credentials for user %s: %s", user.id, exc)
            return None
        return credentials

    def list_events(self, user: User, start: datetime, end: datetime, *, limit: int = 5) -> List[dict]:
        credentials = self._build_credentials(user)
        if not credentials:
            return []

        service = build("calendar", "v3", credentials=credentials, cache_discovery=False)

        time_min = start.astimezone(timezone.utc).isoformat()
        time_max = end.astimezone(timezone.utc).isoformat()

        try:
            events_result = (
                service.events()
                .list(
                    calendarId="primary",
                    timeMin=time_min,
                    timeMax=time_max,
                    singleEvents=True,
                    orderBy="startTime",
                    maxResults=limit,
                )
                .execute()
            )
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("Failed to list Google Calendar events for user %s: %s", user.id, exc)
            return []

        events = events_result.get("items", [])
        formatted = []
        for event in events:
            formatted.append(
                {
                    "id": event.get("id"),
                    "summary": event.get("summary"),
                    "start": event.get("start"),
                    "end": event.get("end"),
                    "htmlLink": event.get("htmlLink"),
                }
            )
        return formatted

    def create_event(
        self,
        user: User,
        *,
        title: str,
        start_ts: datetime,
        end_ts: Optional[datetime] = None,
        description: Optional[str] = None,
    ) -> Optional[dict]:
        credentials = self._build_credentials(user)
        if not credentials:
            return None

        service = build("calendar", "v3", credentials=credentials, cache_discovery=False)

        start_value = start_ts.astimezone(timezone.utc)
        end_value = end_ts.astimezone(timezone.utc) if end_ts else start_value + timedelta(hours=1)

        body = {
            "summary": title,
            "start": {"dateTime": start_value.isoformat(), "timeZone": "UTC"},
            "end": {"dateTime": end_value.isoformat(), "timeZone": "UTC"},
        }
        if description:
            body["description"] = description

        try:
            event = service.events().insert(calendarId="primary", body=body).execute()
            return event
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("Failed to create Google Calendar event for user %s: %s", user.id, exc)
            return None

    def sync_task_event(self, user: User, task: Task, *, due_ts: Optional[datetime]) -> Optional[dict]:
        """Create calendar event for a task when due date is provided."""

        if not due_ts:
            return None

        event = self.create_event(user, title=task.title, start_ts=due_ts)
        if event:
            task.linked_calendar_event_id = event.get("id")
        return event
