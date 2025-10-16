"""API routes for semantic memories."""

from __future__ import annotations

from datetime import datetime
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_db_session, require_api_key
from app.api.dependencies import get_memory_service
from app.db.models import Memory, MemoryTypeEnum
from app.services.memory_service import MemoryService

router = APIRouter(prefix="/memories", tags=["memories"])


class MemoryCreateRequest(BaseModel):
    user_id: uuid.UUID
    type: MemoryTypeEnum
    text: str = Field(..., min_length=1)
    source: Optional[str] = None


class MemoryResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    type: MemoryTypeEnum
    text: str
    source: Optional[str]
    created_at: Optional[datetime]

    model_config = {
        "from_attributes": True,
    }


@router.post("", response_model=MemoryResponse, dependencies=[Depends(require_api_key)])
def create_memory(
    payload: MemoryCreateRequest,
    *,
    session: Session = Depends(get_db_session),
    service: MemoryService = Depends(get_memory_service),
) -> Memory:
    """Create or update a semantic memory for the user."""

    memory = service.save_memory(
        session,
        user_id=payload.user_id,
        memory_type=payload.type,
        text=payload.text,
        source=payload.source,
    )
    session.commit()
    session.refresh(memory)
    return memory


@router.get(
    "/search",
    response_model=List[MemoryResponse],
    dependencies=[Depends(require_api_key)],
)
def search_memories(
    *,
    user_id: uuid.UUID = Query(...),
    q: str = Query(..., min_length=1),
    top_k: int = Query(8, ge=1, le=50),
    session: Session = Depends(get_db_session),
    service: MemoryService = Depends(get_memory_service),
) -> List[Memory]:
    """Search semantic memories with basic relevance."""

    results = service.search_memories(session, user_id=user_id, query=q, top_k=top_k)
    return results
