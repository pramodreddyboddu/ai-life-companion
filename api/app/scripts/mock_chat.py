"""Run a mocked /chat request to verify reminder creation."""

from __future__ import annotations

import json
import uuid

from fastapi.testclient import TestClient
from loguru import logger
from sqlalchemy import select

from app.api.dependencies import get_chat_orchestrator
from app.api.deps import get_db_session
from app.db.models import Reminder, User
from app.db.session import SessionLocal
from app.main import app
from app.services.chat_orchestrator import ChatOrchestrator
from app.services.embedding_service import EmbeddingService
from app.services.memory_service import MemoryService
from app.services.metrics_service import MetricsService


class FakeRateLimiter:
    """Rate limiter stub that never raises."""

    def check(self, user_id: uuid.UUID) -> None:  # noqa: D401
        return None


class FakeChatClient:
    """Deterministic chat completion stub to exercise reminder flow."""

    def __init__(self) -> None:
        self._call_count = 0

    def create(self, *args, **kwargs):  # noqa: D401
        self._call_count += 1
        if self._call_count == 1:
            return _FakeResponse(
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "tool-call-1",
                            "type": "function",
                            "function": {
                                "name": "schedule_reminder",
                                "arguments": json.dumps(
                                    {
                                        "text": "Drink a glass of water.",
                                        "run_ts": "2099-01-01T15:00:00Z",
                                    }
                                ),
                            },
                        }
                    ],
                }
            )
        return _FakeResponse({"role": "assistant", "content": "Reminder scheduled. Next step: sip water at 15:00."})


class _FakeResponse:
    def __init__(self, message: dict) -> None:
        self.choices = [type("Choice", (), {"message": type("Message", (), message)})()]


def run_mock_chat(api_key: str) -> None:
    session = SessionLocal()
    try:
        user = session.execute(select(User).where(User.email == "demo@example.com")).scalar_one_or_none()
        if user is None:
            raise RuntimeError("Demo user missing; run seed first.")
        before_count = session.query(Reminder).count()
    finally:
        session.close()

    embeddings = EmbeddingService(embed_batch_fn=lambda inputs: [[0.0] * 1536 for _ in inputs])
    memo_service = MemoryService(embeddings)
    metrics = MetricsService()
    orchestrator = ChatOrchestrator(
        openai_client=FakeChatClient(),
        embedding_service=embeddings,
        memory_service=memo_service,
        rate_limiter=FakeRateLimiter(),  # type: ignore[arg-type]
        metrics_service=metrics,
        calendar_service=None,
        safety_service=None,
        model="stub",
    )

    existing_overrides = dict(app.dependency_overrides)
    app.dependency_overrides[get_chat_orchestrator] = lambda: orchestrator

    try:
        client = TestClient(app)
        response = client.post(
            "/chat",
            headers={"X-API-Key": api_key},
            json={"message": "Please remind me to drink water later.", "persona_key": "accountability"},
        )
        if response.status_code != 200:
            raise RuntimeError(f"Chat endpoint failed: {response.status_code} {response.text}")
    finally:
        app.dependency_overrides = existing_overrides

    session = SessionLocal()
    try:
        reminder_count = session.query(Reminder).count()
    finally:
        session.close()

    if reminder_count <= before_count:
        raise RuntimeError("Reminder not created by mock chat.")
    logger.info("Mock chat succeeded; reminder count=%s (before=%s).", reminder_count, before_count)


def main() -> None:
    api_key = "sk-demo-accountability"
    run_mock_chat(api_key)


if __name__ == "__main__":
    main()
