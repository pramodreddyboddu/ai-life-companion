"""FastAPI application entrypoint."""

from __future__ import annotations

from fastapi import FastAPI
from loguru import logger

from app.api.agenda import router as agenda_router
from app.api.billing import router as billing_router
from app.api.stt import router as stt_router
from app.api.users import router as users_router
from app.api.memory import router as memory_router
from app.api.routers.chat import router as chat_router
from app.api.routers.oauth import router as oauth_router
from app.settings import settings


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    application = FastAPI(title="AI Companion API", version="0.1.0")
    application.include_router(memory_router)
    application.include_router(chat_router)
    application.include_router(agenda_router)
    application.include_router(stt_router)
    application.include_router(users_router)
    application.include_router(billing_router)
    application.include_router(oauth_router)

    @application.get("/health")
    async def health_check() -> dict[str, str]:
        """Return a simple health payload for readiness probes."""

        return {"status": "ok"}

    logger.info("Running environment: {}", settings.environment)
    return application


app = create_app()
