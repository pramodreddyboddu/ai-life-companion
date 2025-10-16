"""Minimal analytics utilities for custom metrics."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, Optional
import uuid

from loguru import logger
from sqlalchemy import select, func, and_

from app.db.models import MetricsDaily, MetricsEvent
from app.db.session import SessionLocal


class MetricsService:
    """Persist lightweight analytics events and aggregates."""

    def __init__(self, session_factory=SessionLocal) -> None:
        self._session_factory = session_factory

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

            # Retained if active on target_date.
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
