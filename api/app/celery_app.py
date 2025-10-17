"""Celery configuration for background workers."""

from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.logging import configure_logging
from app.settings import settings

configure_logging()


celery_app = Celery(
    "ai_companion",
    broker=settings.redis.url,
    backend=settings.redis.url,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    task_default_queue="default",
    broker_connection_retry_on_startup=True,
    beat_schedule={
        "send-due-reminders": {
            "task": "app.tasks.reminders.send_due_reminders",
            "schedule": 60.0,
        },
        "compute-daily-metrics": {
            "task": "app.tasks.analytics.compute_daily_metrics",
            "schedule": crontab(minute=0, hour=1),
        },
    },
)

celery_app.autodiscover_tasks(["app.tasks"])


@celery_app.task
def ping() -> str:
    """Simple ping task used for health checks."""

    return "pong"
