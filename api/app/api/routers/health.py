"""Health and readiness checks for the API."""

from __future__ import annotations

import contextlib
from typing import Dict

from fastapi import APIRouter, Depends
from loguru import logger
from redis import Redis
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_db_session
from app.celery_app import celery_app
from app.settings import settings

router = APIRouter(tags=["health"])


def _check_db(session: Session) -> str:
    try:
        session.execute(text("SELECT 1"))
        return "ok"
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("DB health check failed: {}", exc)
        return f"fail: {exc}"


def _check_redis() -> str:
    try:
        client = Redis.from_url(settings.redis.url)
        with contextlib.closing(client):
            client.ping()
        return "ok"
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("Redis health check failed: {}", exc)
        return f"fail: {exc}"


def _check_celery() -> str:
    try:
        inspect = celery_app.control.inspect(timeout=2.0)
        stats = inspect.ping() if inspect else None
        if stats:
            return "ok"
        return "fail: no workers"
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("Celery health check failed: {}", exc)
        return f"fail: {exc}"


@router.get("/health")
def health() -> Dict[str, str]:
    """Simple health endpoint for legacy probes."""

    return {"status": "ok"}


@router.get("/healthz")
def healthz(session: Session = Depends(get_db_session)) -> Dict[str, str]:
    """Perform readiness checks for DB, Redis, and Celery."""

    db_status = _check_db(session)
    redis_status = _check_redis()
    celery_status = _check_celery()

    return {
        "db": db_status,
        "redis": redis_status,
        "celery": celery_status,
    }
