"""Chat orchestration endpoints."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.dependencies import get_chat_orchestrator
from app.api.deps import get_db_session, require_api_key
from app.db.models import ApiKey
from app.services.chat_orchestrator import ChatOrchestrator, PersonaNotFoundError

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    persona_key: Optional[str] = Field(default=None, description="Which persona should respond.")


class ChatResponseBody(BaseModel):
    assistant_message: str
    actions: List[Dict[str, Any]]


@router.post("", response_model=ChatResponseBody)
def chat_endpoint(
    payload: ChatRequest,
    *,
    api_key: ApiKey = Depends(require_api_key),
    session: Session = Depends(get_db_session),
    orchestrator: ChatOrchestrator = Depends(get_chat_orchestrator),
) -> ChatResponseBody:
    """Conduct a chat turn and return the assistant reply plus executed actions."""

    try:
        chat_response = orchestrator.handle_chat(
            session=session,
            api_key=api_key,
            message=payload.message,
            persona_key=payload.persona_key,
        )
    except PersonaNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return ChatResponseBody(
        assistant_message=chat_response.assistant_message,
        actions=chat_response.actions,
    )
