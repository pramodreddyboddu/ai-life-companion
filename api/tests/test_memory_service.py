from __future__ import annotations

import hashlib
import math
import uuid
from datetime import datetime, timedelta, timezone
from typing import Sequence

import pytest

from app.db.models import Memory, MemoryTypeEnum, PlanEnum, User
from app.services.embedding_service import EmbeddingService
from app.services.memory_service import MemoryService


class FakeEmbedder:
    """Deterministic embedding generator for tests."""

    def __init__(self, dimensions: int = 1536) -> None:
        self.dimensions = dimensions

    def embed_batch(self, inputs: Sequence[str]) -> Sequence[Sequence[float]]:
        outputs = []
        for text in inputs:
            vector = [0.0] * self.dimensions
            for token in text.lower().split():
                token_hash = hashlib.md5(token.encode("utf-8")).digest()
                index = int.from_bytes(token_hash[:4], "big") % self.dimensions
                vector[index] += 1.0
            norm = math.sqrt(sum(value * value for value in vector))
            if norm > 0:
                vector = [value / norm for value in vector]
            outputs.append(vector)
        return outputs


@pytest.fixture()
def memory_service() -> MemoryService:
    embedder = FakeEmbedder()
    embedding_service = EmbeddingService(embed_batch_fn=embedder.embed_batch)
    return MemoryService(embedding_service)


def test_search_returns_most_relevant_memory(db_session, memory_service: MemoryService) -> None:
    user_id = uuid.uuid4()
    user = User(id=user_id, email="memories@example.com", plan=PlanEnum.FREE)
    db_session.add(user)
    db_session.flush()

    memory_service.save_memory(
        db_session,
        user_id=user_id,
        memory_type=MemoryTypeEnum.NOTE,
        text="Grocery list includes apples and oranges.",
        source="journal",
    )

    old_memory = memory_service.save_memory(
        db_session,
        user_id=user_id,
        memory_type=MemoryTypeEnum.NOTE,
        text="Schedule dentist appointment for next Tuesday.",
        source="tasks",
    )
    assert isinstance(old_memory, Memory)
    old_memory.created_at = datetime.now(timezone.utc) - timedelta(days=7)

    target_memory = memory_service.save_memory(
        db_session,
        user_id=user_id,
        memory_type=MemoryTypeEnum.NOTE,
        text="Discuss roadmap with the product team during the strategy meeting.",
        source="agenda",
    )
    db_session.commit()

    results = memory_service.search_memories(
        db_session,
        user_id=user_id,
        query="product roadmap strategy meeting",
        top_k=3,
    )

    assert len(results) >= 1
    assert results[0].id == target_memory.id
    assert results[0].text == target_memory.text
