"""Service layer for working with semantic memories."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional
import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Memory, MemoryTypeEnum, PlanEnum, User
from app.services.embedding_service import EmbeddingService, cosine_similarity


@dataclass
class MemoryMatch:
    """Search match with associated scoring information."""

    memory: Memory
    score: float
    similarity: float


class MemoryService:
    """High level service coordinating memory persistence and search."""

    def __init__(self, embedding_service: EmbeddingService) -> None:
        self.embedding_service = embedding_service

    def save_memory(
        self,
        session: Session,
        *,
        user_id: uuid.UUID,
        memory_type: MemoryTypeEnum,
        text: str,
        source: Optional[str] = None,
    ) -> Memory:
        """Persist a memory and ensure its embedding is up to date."""

        user = session.get(User, user_id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        if user.plan == PlanEnum.FREE:
            total_memories = session.query(func.count(Memory.id)).filter(Memory.user_id == user_id).scalar() or 0
            if total_memories >= 100:
                raise HTTPException(status_code=402, detail="Upgrade to Pro to store additional memories.")

        memory = self.embedding_service.upsert_memory(
            session,
            user_id=user_id,
            memory_type=memory_type,
            text=text,
            source=source,
        )
        session.flush()
        return memory

    def search_memory_matches(
        self,
        session: Session,
        *,
        user_id: uuid.UUID,
        query: str,
        top_k: int = 8,
    ) -> List[MemoryMatch]:
        """Return scored semantic memory matches for the given query."""

        if not query.strip():
            return []

        query_embedding = self.embedding_service.embed_text(query)

        stmt = select(Memory).where(Memory.user_id == user_id)
        memories = session.execute(stmt).scalars().all()

        now = datetime.now(timezone.utc)
        matches: List[MemoryMatch] = []

        for memory in memories:
            memory_embedding = list(memory.embedding) if memory.embedding is not None else []
            if not memory_embedding:
                continue

            similarity = cosine_similarity(query_embedding, memory_embedding)
            created_at = memory.created_at or now
            age_seconds = max((now - created_at).total_seconds(), 0.0)
            recency_boost = 0.1 / (1.0 + (age_seconds / 86400.0))

            score = similarity + recency_boost
            matches.append(MemoryMatch(memory=memory, score=score, similarity=similarity))

        matches.sort(key=lambda item: item.score, reverse=True)
        return matches[:top_k]

    def search_memories(
        self,
        session: Session,
        *,
        user_id: uuid.UUID,
        query: str,
        top_k: int = 8,
    ) -> List[Memory]:
        """Return the most relevant memories for the requested query."""

        return [match.memory for match in self.search_memory_matches(session, user_id=user_id, query=query, top_k=top_k)]
