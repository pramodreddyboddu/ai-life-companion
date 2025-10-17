"""Minimal analytics utilities for custom metrics and counters."""

from __future__ import annotations

from collections import Counter
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, Optional
import uuid

from loguru import logger
from redis import Redis
from sqlalchemy import and_, func, select

from app.db.models import MetricsDaily, MetricsEvent
from app.db.session import SessionLocal
from app.settings import settings


class MetricsService:
    """Persist lightweight analytics events and aggregates."""

    def __init__(
        self,
        session_factory=SessionLocal,
        *,
        redis_client: Optional[Redis] = None,
        redis_key: str = "metrics:counters",
        histogram_key: str = "metrics:histogram:reminder_latency",
    ) -> None:
        self._session_factory = session_factory
        self._redis_key = redis_key
        self._local_counters: Counter[str] = Counter()
        self._histogram_key = histogram_key
        self._redis: Optional[Redis] = redis_client

        if self._redis is None:
            try:
                self._redis = Redis.from_url(settings.redis.url, decode_responses=True)
            except Exception as exc:  # pylint: disable=broad-except
                self._redis = None
                logger.warning("Metrics counters falling back to in-process storage: {}", exc)

    # --------------------------------------------------------------------- #
    # Lightweight counters (Redis-backed)
    # --------------------------------------------------------------------- #
    def increment_counter(self, name: str, amount: int = 1) -> None:
        """Increment a lightweight counter."""

        if amount == 0:
            return
        if self._redis is not None:
            try:
                self._redis.hincrby(self._redis_key, name, amount)
                return
            except Exception as exc:  # pylint: disable=broad-except
                logger.warning("Failed to increment Redis counter %s: %s (using local fallback)", name, exc)
                self._redis = None  # Avoid repeated Redis attempts until reinitialised
        self._local_counters[name] += amount

    def set_gauge(self, name: str, value: float) -> None:
        """Set a gauge value."""

        if self._redis is not None:
            try:
                self._redis.hset(self._redis_key, name, value)
                return
            except Exception as exc:  # pylint: disable=broad-except
                logger.warning("Failed to set Redis gauge %s: %s (using local fallback)", name, exc)
                self._redis = None
        self._local_counters[name] = value

    def record_latency(self, latency_seconds: float) -> None:
        """Record reminder delivery latency into histogram buckets."""

        buckets = [
            (30, "le_30s"),
            (60, "le_1m"),
            (120, "le_2m"),
            (300, "le_5m"),
            (600, "le_10m"),
            (float("inf"), "le_inf"),
        ]

        for threshold, bucket in buckets:
            if latency_seconds <= threshold:
                self.increment_counter(f"reminder_latency_bucket:{bucket}")
        self.increment_counter("reminder_latency_count")
        self.increment_counter("reminder_latency_sum", amount=int(latency_seconds))

    def get_metrics(self) -> Dict[str, Any]:
        """Return current counter values."""

        counters: Counter[str] = Counter(self._local_counters)
        if self._redis is not None:
            try:
                redis_values = self._redis.hgetall(self._redis_key) or {}
                counters.update({key: int(value) for key, value in redis_values.items()})
            except Exception as exc:  # pylint: disable=broad-except
                logger.warning("Failed to read Redis counters: %s", exc)
        for key in ("reminder_scheduled", "reminder_sent", "reminder_canceled", "reminder_error", "worker_uptime_seconds"):
            counters[key] += 0
        histogram = {k: v for k, v in counters.items() if k.startswith("reminder_latency_bucket:")}
        return {
            "timestamp": time.time(),
            "counters": dict(counters),
            "histogram": histogram,
        }

    # --------------------------------------------------------------------- #
    # Event + retention analytics (existing functionality)
    # --------------------------------------------------------------------- #
    def track(self, event_name: str, *, user_id: uuid.UUID, properties: Optional[Dict[str, Any]] = None) -> None:
        """Persist a single analytics event on a separate transaction."""

        session = self._session_factory()
        try:
            event = MetricsEvent(user_id=user_id, event_name=event_name, properties=properties or {})
            session.add(event)
            session.commit()
        except Exception as exc:  # pylint: disable=broad-except
            session.rollback()
            logger.warning("Failed to record metrics event %s for %s: %s", event_name, user_id, exc)
        finally:
            session.close()

    def compute_retention(self, target_date: date) -> MetricsDaily:
        """Calculate simple retention metrics for the provided date."""

        session = self._session_factory()
        try:
            start_dt = datetime.combine(target_date, datetime.min.time(), tzinfo=timezone.utc)
            end_dt = start_dt + timedelta(days=1)

            # Unique active users on the target date.
            active_users_subq = (
                select(MetricsEvent.user_id)
                .where(
                    and_(
                        MetricsEvent.event_name == "chat_turn",
                        MetricsEvent.created_at >= start_dt,
                        MetricsEvent.created_at < end_dt,
                    )
                )
                .group_by(MetricsEvent.user_id)
            )
            active_users = session.execute(select(func.count()).select_from(active_users_subq.subquery())).scalar() or 0

            # Cohort: users whose first chat_turn was exactly the day before target.
            previous_day = target_date - timedelta(days=1)
            cohort_users_subq = (
                select(MetricsEvent.user_id, func.min(MetricsEvent.created_at).label("first_seen"))
                .where(MetricsEvent.event_name == "chat_turn")
                .group_by(MetricsEvent.user_id)
                .having(func.date(func.min(MetricsEvent.created_at)) == previous_day)
            )
            cohort_users = [row[0] for row in session.execute(cohort_users_subq)]
            cohort_size = len(cohort_users)

            # Retained if active on target date.
            retained_day1 = 0
            if cohort_users:
                retained_query = (
                    select(func.count(func.distinct(MetricsEvent.user_id)))
                    .where(
                        and_(
                            MetricsEvent.event_name == "chat_turn",
                            MetricsEvent.created_at >= start_dt,
                            MetricsEvent.created_at < end_dt,
                            MetricsEvent.user_id.in_(cohort_users),
                        )
                    )
                )
                retained_day1 = session.execute(retained_query).scalar() or 0

            # Day 7 retention using cohort from 7 days prior.
            previous_week = target_date - timedelta(days=7)
            cohort_week_subq = (
                select(MetricsEvent.user_id, func.min(MetricsEvent.created_at).label("first_seen"))
                .where(MetricsEvent.event_name == "chat_turn")
                .group_by(MetricsEvent.user_id)
                .having(func.date(func.min(MetricsEvent.created_at)) == previous_week)
            )
            cohort_week_users = [row[0] for row in session.execute(cohort_week_subq)]
            retained_day7 = 0
            if cohort_week_users:
                retained_week_query = (
                    select(func.count(func.distinct(MetricsEvent.user_id)))
                    .where(
                        and_(
                            MetricsEvent.event_name == "chat_turn",
                            MetricsEvent.created_at >= start_dt,
                            MetricsEvent.created_at < end_dt,
                            MetricsEvent.user_id.in_(cohort_week_users),
                        )
                    )
                )
                retained_day7 = session.execute(retained_week_query).scalar() or 0

            record = (
                session.execute(
                    select(MetricsDaily).where(MetricsDaily.metrics_date == target_date)
                ).scalar_one_or_none()
            )
            if record is None:
                record = MetricsDaily(metrics_date=target_date)
                session.add(record)

            record.cohort_size = cohort_size
            record.retained_day1 = retained_day1
            record.retained_day7 = retained_day7
            record.active_users = active_users
            record.retention_rate_day1 = retained_day1 / cohort_size if cohort_size else None
            record.retention_rate_day7 = retained_day7 / len(cohort_week_users) if cohort_week_users else None
            session.commit()
            return record
        except Exception as exc:  # pylint: disable=broad-except
            session.rollback()
            logger.error("Failed to compute retention for %s: %s", target_date, exc)
            raise
        finally:
            session.close()
