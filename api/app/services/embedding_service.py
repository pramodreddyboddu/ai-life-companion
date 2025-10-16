"""Embedding service wrapping OpenAI embeddings and memory upsert."""

from __future__ import annotations

import math
from typing import Callable, Iterable, List, Optional, Sequence
import uuid

from openai import OpenAI
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Memory, MemoryTypeEnum


EmbedBatchFn = Callable[[Sequence[str]], Sequence[Sequence[float]]]


class EmbeddingService:
    """Service responsible for generating embeddings and persisting memories."""

    def __init__(
        self,
        *,
        client: Optional[OpenAI] = None,
        model: str = "text-embedding-3-small",
        max_tokens: int = 800,
        embed_batch_fn: Optional[EmbedBatchFn] = None,
    ) -> None:
        self._client: Optional[OpenAI] = client
        self.model = model
        self.max_tokens = max_tokens
        self._embed_batch_fn = embed_batch_fn
        if self._client is None and self._embed_batch_fn is None:
            self._client = OpenAI()

    def chunk_text(self, text: str) -> List[str]:
        """Split text into chunks of approximately max_tokens words."""

        words = text.split()
        if not words:
            return [text]

        chunks: List[str] = []
        current: List[str] = []

        for word in words:
            current.append(word)
            if len(current) >= self.max_tokens:
                chunks.append(" ".join(current))
                current = []

        if current:
            chunks.append(" ".join(current))

        return chunks

    def embed_text(self, text: str) -> List[float]:
        """Return the averaged embedding vector for the provided text."""

        chunks = self.chunk_text(text)
        embeddings = self._embed_chunks(chunks)
        return self._average_embeddings(embeddings)

    def upsert_memory(
        self,
        session: Session,
        *,
        user_id: uuid.UUID,
        memory_type: MemoryTypeEnum,
        text: str,
        source: Optional[str],
    ) -> Memory:
        """Create or update a memory record with the latest embedding."""

        embedding = self.embed_text(text)

        stmt = select(Memory).where(Memory.user_id == user_id, Memory.type == memory_type)
        if source is not None:
            stmt = stmt.where(Memory.source == source)
        else:
            stmt = stmt.where(Memory.source.is_(None), Memory.text == text)

        existing = session.execute(stmt.limit(1)).scalar_one_or_none()

        if existing:
            existing.text = text
            existing.source = source
            existing.embedding = embedding
            session.flush()
            return existing

        memory = Memory(
            user_id=user_id,
            type=memory_type,
            text=text,
            source=source,
            embedding=embedding,
        )
        session.add(memory)
        session.flush()
        return memory

    def _embed_chunks(self, chunks: Sequence[str]) -> List[List[float]]:
        if self._embed_batch_fn is not None:
            embeddings = self._embed_batch_fn(chunks)
            return [list(embedding) for embedding in embeddings]

        if self._client is None:
            raise RuntimeError("Embedding client is not configured.")

        response = self._client.embeddings.create(model=self.model, input=list(chunks))
        return [list(item.embedding) for item in response.data]

    @staticmethod
    def _average_embeddings(embeddings: Iterable[Sequence[float]]) -> List[float]:
        embeddings_list = list(embeddings)
        if not embeddings_list:
            raise ValueError("No embeddings provided for averaging.")

        length = len(embeddings_list[0])
        sums = [0.0] * length

        for vector in embeddings_list:
            if len(vector) != length:
                raise ValueError("Embedding dimensions mismatch during averaging.")
            for idx, value in enumerate(vector):
                sums[idx] += value

        count = float(len(embeddings_list))
        return [value / count for value in sums]


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    """Compute cosine similarity between two vectors."""

    if len(left) != len(right):
        raise ValueError("Vectors must be of same dimensions for cosine similarity.")

    dot = sum(a * b for a, b in zip(left, right))
    norm_left = math.sqrt(sum(a * a for a in left))
    norm_right = math.sqrt(sum(b * b for b in right))

    if norm_left == 0 or norm_right == 0:
        return 0.0

    return dot / (norm_left * norm_right)
