"""API routes for semantic memory creation and search."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_db_session, require_api_key
from app.api.dependencies import get_memory_service
from app.db.models import ApiKey, Memory, MemoryTypeEnum
from app.services.memory_service import MemoryService

router = APIRouter(tags=["memories"])


class MemoryUpsertRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000)
    type: MemoryTypeEnum = MemoryTypeEnum.NOTE
    source: Optional[str] = Field(default=None, max_length=255)


class MemoryResponse(BaseModel):
    id: str
    text: str
    type: MemoryTypeEnum
    source: Optional[str]
    created_at: Optional[datetime]

    model_config = {"from_attributes": True}


class MemorySearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)
    top_k: int = Field(5, ge=1, le=50)


class MemorySearchResult(BaseModel):
    id: str
    text: str
    type: MemoryTypeEnum
    source: Optional[str]
    created_at: Optional[datetime]
    score: float = Field(..., ge=-1.0, le=2.0)
    similarity: float = Field(..., ge=-1.0, le=1.0)

    model_config = {"from_attributes": True}


def _to_response(memory: Memory) -> MemoryResponse:
    return MemoryResponse(
        id=str(memory.id),
        text=memory.text,
        type=memory.type,
        source=memory.source,
        created_at=memory.created_at,
    )


@router.post("/memory", response_model=MemoryResponse)
def create_memory(
    payload: MemoryUpsertRequest,
    *,
    api_key: ApiKey = Depends(require_api_key),
    session: Session = Depends(get_db_session),
    service: MemoryService = Depends(get_memory_service),
) -> MemoryResponse:
    """Embed and upsert a semantic memory for the authenticated user."""

    memory = service.save_memory(
        session,
        user_id=api_key.user_id,
        memory_type=payload.type,
        text=payload.text,
        source=payload.source,
    )
    session.commit()
    session.refresh(memory)
    return _to_response(memory)


@router.post("/memory/search", response_model=List[MemorySearchResult])
def search_memory(
    payload: MemorySearchRequest,
    *,
    api_key: ApiKey = Depends(require_api_key),
    session: Session = Depends(get_db_session),
    service: MemoryService = Depends(get_memory_service),
) -> List[MemorySearchResult]:
    """Return top-k semantic memories for the authenticated user."""

    matches = service.search_memory_matches(
        session,
        user_id=api_key.user_id,
        query=payload.query,
        top_k=payload.top_k,
    )
    return [
        MemorySearchResult(
            id=str(match.memory.id),
            text=match.memory.text,
            type=match.memory.type,
            source=match.memory.source,
            created_at=match.memory.created_at,
            score=match.score,
            similarity=match.similarity,
        )
        for match in matches
    ]


# Legacy endpoints (kept for backwards compatibility)
@router.post(
    "/memories",
    response_model=MemoryResponse,
    dependencies=[Depends(require_api_key)],
    include_in_schema=False,
)
def legacy_create_memory(
    payload: MemoryUpsertRequest,
    *,
    api_key: ApiKey = Depends(require_api_key),
    session: Session = Depends(get_db_session),
    service: MemoryService = Depends(get_memory_service),
) -> MemoryResponse:
    return create_memory(payload, api_key=api_key, session=session, service=service)


@router.post(
    "/memories/search",
    response_model=List[MemorySearchResult],
    dependencies=[Depends(require_api_key)],
    include_in_schema=False,
)
def legacy_search_memory(
    payload: MemorySearchRequest,
    *,
    api_key: ApiKey = Depends(require_api_key),
    session: Session = Depends(get_db_session),
    service: MemoryService = Depends(get_memory_service),
) -> List[MemorySearchResult]:
    return search_memory(payload, api_key=api_key, session=session, service=service)
