"""FastAPI application entrypoint with structured logging."""

from __future__ import annotations

import uuid

from fastapi import FastAPI, Request
from loguru import logger

from app.api.agenda import router as agenda_router
from app.api.billing import router as billing_router
from app.api.memory import router as memory_router
from app.api.routers.calendar import router as calendar_router
from app.api.routers.admin import router as admin_router
from app.api.routers.chat import router as chat_router
from app.api.routers.health import router as health_router
from app.api.routers.metrics import router as metrics_router
from app.api.routers.oauth import router as oauth_router
from app.api.stt import router as stt_router
from app.api.users import router as users_router
from app.logging import configure_logging, correlation_scope
from app.settings import settings

configure_logging()


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
    application.include_router(metrics_router)
    application.include_router(health_router)

    @application.middleware("http")
    async def inject_correlation_id(request: Request, call_next):
        correlation_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        with correlation_scope(correlation_id):
            response = await call_next(request)
        response.headers["X-Request-ID"] = correlation_id
        return response

    logger.info("Running environment: {}", settings.environment)
    return application


app = create_app()
