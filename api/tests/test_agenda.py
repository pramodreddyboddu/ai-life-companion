from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_calendar_service
from app.api.deps import get_db_session
from app.db.models import ApiKey, ApiKeyStatusEnum, PlanEnum, User
from app.main import app
from app.security.api_keys import get_key_prefix, hash_api_key


class DummyCalendarService:
    def list_events(self, user, start, end, limit=5):  # noqa: D401
        return [
            {
                "id": "evt-1",
                "summary": "Standup",
                "start": {"dateTime": start.isoformat()},
                "end": {"dateTime": end.isoformat()},
                "htmlLink": "https://calendar.google.com/event?evt-1",
            }
        ]


@pytest.fixture()
def agenda_client(db_session):
    def override_db_session():
        return db_session

    app.dependency_overrides[get_db_session] = override_db_session
    app.dependency_overrides[get_calendar_service] = lambda: DummyCalendarService()
    client = TestClient(app)
    try:
        yield client
    finally:
        client.close()
        app.dependency_overrides.clear()


def test_agenda_endpoint_returns_events(agenda_client, db_session):
    user = User(id=uuid.uuid4(), email="agenda@example.com", plan=PlanEnum.PRO)
    db_session.add(user)
    api_key_value = "sk-agenda-test"
    api_key = ApiKey(
        user_id=user.id,
        prefix=get_key_prefix(api_key_value),
        key_hash=hash_api_key(api_key_value),
        status=ApiKeyStatusEnum.ACTIVE,
    )
    db_session.add(api_key)
    db_session.commit()

    response = agenda_client.get(
        "/agenda",
        headers={"X-API-Key": api_key_value},
        params={"from": datetime.now(timezone.utc).isoformat()},
    )
    assert response.status_code == 200
    payload = response.json()
    assert "events" in payload
    assert payload["events"][0]["id"] == "evt-1"
