"""Logging utilities providing JSON output and correlation IDs."""

from __future__ import annotations

import sys
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime
from typing import Any, Dict, Generator, Optional

from loguru import logger

_CORRELATION_ID: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)


def configure_logging() -> None:
    """Configure loguru to emit JSON logs to stdout."""

    logger.remove()
    logger.add(sys.stdout, enqueue=True, serialize=True, backtrace=False, diagnose=False)


def get_correlation_id() -> Optional[str]:
    """Return the correlation ID for the current context, if any."""

    return _CORRELATION_ID.get()


@contextmanager
def correlation_scope(correlation_id: Optional[str] = None) -> Generator[None, None, None]:
    """Context manager that sets a correlation ID for the duration of the scope."""

    cid = correlation_id or get_correlation_id() or str(uuid.uuid4())
    token = _CORRELATION_ID.set(cid)
    with logger.contextualize(correlation_id=cid):
        try:
            yield
        finally:
            _CORRELATION_ID.reset(token)


def ensure_correlation_id(default: Optional[str] = None) -> str:
    """Return the active correlation ID, setting one if absent."""

    cid = get_correlation_id()
    if cid:
        return cid
    cid = default or str(uuid.uuid4())
    _CORRELATION_ID.set(cid)
    return cid


def log_reminder_event(
    event: str,
    *,
    user_id: Optional[uuid.UUID],
    reminder_id: uuid.UUID,
    eta_utc: Optional[datetime],
    status: str,
    level: str = "INFO",
    **extra: Any,
) -> None:
    """Emit a structured log line for a reminder lifecycle event."""

    payload: Dict[str, Any] = {
        "event": event,
        "user_id": str(user_id) if user_id else None,
        "reminder_id": str(reminder_id),
        "eta_utc": eta_utc.isoformat() if eta_utc else None,
        "status": status,
    }
    payload.update({key: value for key, value in extra.items() if value is not None})

    cleaned = {key: value for key, value in payload.items() if value is not None}
    logger.bind(**cleaned).log(level, event)


__all__ = [
    "configure_logging",
    "correlation_scope",
    "ensure_correlation_id",
    "get_correlation_id",
    "log_reminder_event",
]
