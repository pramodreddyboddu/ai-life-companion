from __future__ import annotations

import json
import uuid
from typing import Any, Dict, List

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_chat_orchestrator
from app.api.deps import get_db_session
from app.db.models import ApiKey, ApiKeyStatusEnum, Persona, Reminder, User, PlanEnum
from app.main import app
from app.security.api_keys import get_key_prefix, hash_api_key
from app.services.chat_orchestrator import ChatOrchestrator, DEFAULT_PERSONAS
from app.services.embedding_service import EmbeddingService
from app.services.memory_service import MemoryService
from app.services.safety import SafetyResult
from app.services.metrics_service import MetricsService


class FakeChatCompletions:
    """Deterministic OpenAI chat completion stub with tool calling."""

    def __init__(self) -> None:
        self._call_count = 0

    def create(self, *args: Any, **kwargs: Any):
        self._call_count += 1
        if self._call_count == 1:
            tool_call = _FakeToolCall(
                name="schedule_reminder",
                arguments=json.dumps(
                    {
                        "text": "Drink a glass of water.",
                        "run_ts": "2024-05-20T15:00:00Z",
                    }
                ),
            )
            message = _FakeMessage(content=None, tool_calls=[tool_call])
            return _FakeResponse(message)

        message = _FakeMessage(content="Reminder set for 3pm to drink water. I've got you covered!")
        return _FakeResponse(message)


class _FakeToolFunction:
    def __init__(self, name: str, arguments: str) -> None:
        self.name = name
        self.arguments = arguments


class _FakeToolCall:
    def __init__(self, name: str, arguments: str) -> None:
        self.id = "tool-call-1"
        self.type = "function"
        self.function = _FakeToolFunction(name, arguments)


class _FakeMessage:
    def __init__(self, *, content: str | None, tool_calls: List[_FakeToolCall] | None = None) -> None:
        self.content = content
        self.tool_calls = tool_calls or []


class _FakeChoice:
    def __init__(self, message: _FakeMessage) -> None:
        self.message = message


class _FakeResponse:
    def __init__(self, message: _FakeMessage) -> None:
        self.choices = [_FakeChoice(message)]


class NoOpRateLimiter:
    def check(self, _user_id: uuid.UUID) -> None:
        return None


class DummyCalendarService:
    def list_events(self, *args, **kwargs):  # noqa: D401
        return []

    def sync_task_event(self, *args, **kwargs):  # noqa: D401
        return None


class AllowSafetyService:
    def evaluate(self, message: str) -> SafetyResult:
        return SafetyResult(allowed=True)


class BlockSafetyService:
    def __init__(self, response: str) -> None:
        self._response = response

    def evaluate(self, message: str) -> SafetyResult:
        return SafetyResult(allowed=False, response=self._response, reason="blocked")


def constant_embedder(inputs: List[str]) -> List[List[float]]:
    return [[0.0] * 1536 for _ in inputs]


class MetricsStub(MetricsService):
    def __init__(self) -> None:
        self.events: List[Dict[str, Any]] = []

    def track(self, event_name: str, *, user_id: uuid.UUID, properties: Dict[str, Any] | None = None) -> None:
        self.events.append(
            {
                "name": event_name,
                "user_id": user_id,
                "properties": properties or {},
            }
        )


def _ensure_persona(db_session, *, key: str, name: str, system_prompt: str) -> Persona:
    persona = db_session.query(Persona).filter(Persona.key == key).one_or_none()
    if persona is None:
        persona = Persona(key=key, name=name, system_prompt=system_prompt)
        db_session.add(persona)
    else:
        persona.name = name
        persona.system_prompt = system_prompt
    db_session.flush()
    return persona


@pytest.fixture()
def client(db_session):
    def override_db_session():
        return db_session

    app.dependency_overrides[get_db_session] = override_db_session
    test_client = TestClient(app)
    try:
        yield test_client
    finally:
        test_client.close()
        app.dependency_overrides.clear()


def _install_chat_override(safety_service=None, metrics_service: MetricsService | None = None) -> ChatOrchestrator:
    fake_embeddings = EmbeddingService(embed_batch_fn=constant_embedder)
    memory_service = MemoryService(fake_embeddings)
    orchestrator = ChatOrchestrator(
        openai_client=FakeChatCompletions(),
        embedding_service=fake_embeddings,
        memory_service=memory_service,
        rate_limiter=NoOpRateLimiter(),
        metrics_service=metrics_service or MetricsStub(),
        calendar_service=DummyCalendarService(),
        safety_service=safety_service or AllowSafetyService(),
        model="test-model",
    )

    app.dependency_overrides[get_chat_orchestrator] = lambda: orchestrator
    return orchestrator


def test_chat_creates_reminder_and_returns_confirmation(client, db_session) -> None:
    user = User(id=uuid.uuid4(), email="user@example.com", plan=PlanEnum.FREE)
    db_session.add(user)

    api_key_value = "sk-test-chat-key-1"
    api_key = ApiKey(
        user_id=user.id,
        prefix=get_key_prefix(api_key_value),
        key_hash=hash_api_key(api_key_value),
        status=ApiKeyStatusEnum.ACTIVE,
    )
    db_session.add(api_key)
    _ensure_persona(db_session, key="coach", name="Coach", system_prompt="You are supportive.")

    metrics_stub = MetricsStub()
    orchestrator = _install_chat_override(metrics_service=metrics_stub)

    response = client.post(
        "/chat",
        headers={"X-API-Key": api_key_value},
        json={"message": "Please remind me to drink water at 3pm.", "persona_key": "coach"},
    )

    assert response.status_code == 200
    body = response.json()
    assert "drink water" in body["assistant_message"].lower()

    actions = body["actions"]
    assert actions, "Expected at least one action."
    first_action = actions[0]
    assert first_action["tool"] == "schedule_reminder"
    assert first_action["params"]["text"] == "Drink a glass of water."

    reminders = db_session.query(Reminder).filter(Reminder.user_id == user.id).all()
    assert len(reminders) == 1
    assert reminders[0].text == "Drink a glass of water."
    assert reminders[0].run_ts.isoformat().startswith("2024-05-20T15:00:00")

    event_names = [event["name"] for event in metrics_stub.events]
    assert "reminder_created" in event_names
    assert "chat_turn" in event_names
    persona_events = [event for event in metrics_stub.events if event["name"] == "persona_changed"]
    assert persona_events, "Expected persona change to be logged."


def test_accountability_persona_prompt_updates(client, db_session) -> None:
    expected_prompt = DEFAULT_PERSONAS["accountability"]["system_prompt"]

    user = User(id=uuid.uuid4(), email="accountability@example.com", plan=PlanEnum.FREE)
    db_session.add(user)

    api_key_value = "sk-test-accountability"
    api_key = ApiKey(
        user_id=user.id,
        prefix=get_key_prefix(api_key_value),
        key_hash=hash_api_key(api_key_value),
        status=ApiKeyStatusEnum.ACTIVE,
    )
    db_session.add(api_key)

    legacy_persona = _ensure_persona(
        db_session,
        key="accountability",
        name="Accountability",
        system_prompt="Legacy prompt",
    )

    metrics_stub = MetricsStub()
    _install_chat_override(metrics_service=metrics_stub)

    response = client.post(
        "/chat",
        headers={"X-API-Key": api_key_value},
        json={"message": "Help me stay on track tomorrow.", "persona_key": "accountability"},
    )

    assert response.status_code == 200

    db_session.refresh(legacy_persona)
    assert legacy_persona.system_prompt == expected_prompt
    assert legacy_persona.name == "Accountability"

    persona_changes = [event for event in metrics_stub.events if event["name"] == "persona_changed"]
    assert persona_changes, "Expected persona change to be recorded."

def test_chat_safety_blocks_request(client, db_session):
    user = User(id=uuid.uuid4(), email="safety@example.com", plan=PlanEnum.FREE)
    db_session.add(user)
    api_key_value = "sk-test-safety"
    api_key = ApiKey(
        user_id=user.id,
        prefix=get_key_prefix(api_key_value),
        key_hash=hash_api_key(api_key_value),
        status=ApiKeyStatusEnum.ACTIVE,
    )
    db_session.add(api_key)
    _ensure_persona(db_session, key="coach", name="Coach", system_prompt="Prompt")

    message = "I want to hurt myself"

    metrics_stub = MetricsStub()
    _install_chat_override(safety_service=BlockSafetyService("Please reach out for help."), metrics_service=metrics_stub)

    try:
        response = client.post(
            "/chat",
            headers={"X-API-Key": api_key_value},
            json={"message": message, "persona_key": "coach"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert "reach out" in payload["assistant_message"].lower()
        assert payload.get("actions") == []
    finally:
        app.dependency_overrides.clear()
    blocked_events = [event for event in metrics_stub.events if event["name"] == "chat_turn" and event["properties"].get("blocked")]
    assert blocked_events, "Blocked chat turn should be tracked."


def test_log_redaction(monkeypatch):
    from app.services import chat_orchestrator as chat_module

    fake_embeddings = EmbeddingService(embed_batch_fn=constant_embedder)
    memory_service = MemoryService(fake_embeddings)
    orchestrator = ChatOrchestrator(
        openai_client=FakeChatCompletions(),
        embedding_service=fake_embeddings,
        memory_service=memory_service,
        rate_limiter=NoOpRateLimiter(),
        calendar_service=DummyCalendarService(),
        safety_service=AllowSafetyService(),
        metrics_service=MetricsStub(),
        model="test-model",
    )

    captured: List[str] = []

    def fake_info(message, *args, **kwargs):
        captured.append(message.format(*args))

    monkeypatch.setattr(chat_module.logger, "info", fake_info)

    user = User(id=uuid.uuid4(), email="log@example.com", plan=PlanEnum.FREE)
    orchestrator._log_user_message(user, "Contact me at test@example.com or +1 212-555-7890")

    assert captured
    assert "[REDACTED_EMAIL]" in captured[0]
    assert "[REDACTED_PHONE]" in captured[0]
