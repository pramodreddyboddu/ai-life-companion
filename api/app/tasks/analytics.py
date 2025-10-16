"""Celery tasks for analytics aggregation."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Optional

from loguru import logger

from app.celery_app import celery_app
from app.services.metrics_service import MetricsService


@celery_app.task(bind=True, name="app.tasks.analytics.compute_daily_metrics")
def compute_daily_metrics(self, target_date_iso: Optional[str] = None) -> str:
    """Compute daily retention metrics for the provided date (defaults to yesterday UTC)."""

    try:
        if target_date_iso:
            target_date = date.fromisoformat(target_date_iso)
        else:
            target_date = (datetime.now(timezone.utc) - timedelta(days=1)).date()
    except ValueError as exc:
        raise ValueError(f"Invalid date format: {target_date_iso}") from exc

    metrics_service = MetricsService()
    record = metrics_service.compute_retention(target_date)
    logger.info(
        "Computed metrics for %s: cohort_size=%s retained_day1=%s retained_day7=%s active=%s",
        target_date,
        record.cohort_size,
        record.retained_day1,
        record.retained_day7,
        record.active_users,
    )
    return str(record.id)

