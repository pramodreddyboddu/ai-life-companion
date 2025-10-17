"""Celery tasks for delivering reminders."""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

import httpx
from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.celery_app import celery_app
from app.db.models import FailedJob, Reminder, ReminderStatusEnum, User
from app.db.session import SessionLocal
from app.logging import correlation_scope, ensure_correlation_id, log_reminder_event
from app.services.metrics_service import MetricsService
from app.services.feature_flags import FeatureFlagService
from app.settings import settings

RESEND_API_URL = "https://api.resend.com/emails"
EXPO_PUSH_URL = settings.expo_push_url or "https://exp.host/--/api/v2/push/send"
MAX_RETRIES = 5

METRICS = MetricsService()
FEATURE_FLAGS = FeatureFlagService()



def _parse_time(current_time_iso: Optional[str]) -> datetime:
    if current_time_iso is None:
        return datetime.now(timezone.utc)
    if isinstance(current_time_iso, datetime):
        value = current_time_iso
    else:
        iso_value = current_time_iso.strip()
        if iso_value.endswith("Z"):
            iso_value = iso_value[:-1] + "+00:00"
        value = datetime.fromisoformat(iso_value)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def send_email_notification(user: User, reminder: Reminder) -> bool:
    """Send a reminder email via Resend."""

    if not settings.resend_api_key or not settings.resend_from_email:
        logger.debug("Skipping email notification; Resend configuration missing.")
        return False

    if not user.email:
        logger.debug("Skipping email notification; user %s is missing an email address.", user.id)
        return False

    payload = {
        "from": settings.resend_from_email,
        "to": user.email,
        "subject": "AI Companion Reminder",
        "text": reminder.text,
    }

    headers = {
        "Authorization": f"Bearer {settings.resend_api_key}",
        "Content-Type": "application/json",
    }

    try:
        response = httpx.post(RESEND_API_URL, headers=headers, json=payload, timeout=10.0)
        if response.status_code < 300:
            return True
        logger.warning(
            "Failed to send Resend email for reminder %s: %s",
            reminder.id,
            response.text,
        )
    except httpx.HTTPError as exc:
        logger.exception("HTTP error while sending Resend email: %s", exc)
    return False


def send_push_notification(user: User, reminder: Reminder) -> bool:
    """Send a push notification via Expo."""

    if not settings.expo_access_token:
        logger.debug("Skipping push notification; Expo access token missing.")
        return False

    if not user.push_token:
        logger.debug("Skipping push notification; user %s has no push token.", user.id)
        return False

    headers = {
        "Authorization": f"Bearer {settings.expo_access_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "to": user.push_token,
        "title": "Reminder",
        "body": reminder.text,
    }

    try:
        response = httpx.post(EXPO_PUSH_URL, headers=headers, json=payload, timeout=10.0)
        if response.status_code < 300:
            return True
        logger.warning(
            "Failed to send Expo push for reminder %s: %s",
            reminder.id,
            response.text,
        )
    except httpx.HTTPError as exc:
        logger.exception("HTTP error while sending Expo push: %s", exc)
    return False


def _record_failed_job(session, job_name: str, payload: Dict[str, str], error_message: str, attempts: int) -> None:
    failed_job = FailedJob(
        job_name=job_name,
        payload=payload,
        error_message=error_message,
        attempts=attempts,
        last_error_at=datetime.now(timezone.utc),
    )
    session.add(failed_job)


def dispatch_notifications(user: User, reminder: Reminder) -> bool:
    """Send the reminder over available notification channels."""

    if not FEATURE_FLAGS.is_enabled("multi_channel_notifications"):
        logger.info("Multi-channel notifications disabled via feature flag.")
        return True

    attempts: List[bool] = []

    email_possible = bool(settings.resend_api_key and settings.resend_from_email and user.email)
    push_possible = bool(settings.expo_access_token and user.push_token)

    if email_possible:
        attempts.append(send_email_notification(user, reminder))
    if push_possible:
        attempts.append(send_push_notification(user, reminder))

    if not attempts:
        logger.warning("No notification channels available for user %s reminder %s.", user.id, reminder.id)
        return False

    return any(attempts)


def attempt_delivery(session: Session, reminder: Reminder, user: User, now: datetime) -> None:
    """Attempt to deliver the reminder via available channels."""

    reminder.last_attempt_at = now
    session.flush()

    delivered = dispatch_notifications(user, reminder)
    if not delivered:
        raise RuntimeError(f"No notification channel succeeded for reminder {reminder.id}")

    reminder.status = ReminderStatusEnum.SENT
    reminder.sent_at = now
    log_reminder_event(
        "reminder_fired",
        user_id=user.id,
        reminder_id=reminder.id,
        eta_utc=reminder.utc_ts,
        status=reminder.status.value,
    )
    latency = max((now - reminder.utc_ts).total_seconds(), 0.0) if reminder.utc_ts else 0.0
    METRICS.record_latency(latency)
    METRICS.increment_counter("reminder_sent")

def schedule_due_reminders(current_time: datetime, session: Optional[Session] = None) -> List[uuid.UUID]:
    """Find due reminders and enqueue delivery tasks."""

    owns_session = session is None
    if owns_session:
        session = SessionLocal()

    scheduled_ids: List[uuid.UUID] = []
    try:
        stmt = (
            select(Reminder)
            .where(Reminder.status == ReminderStatusEnum.SCHEDULED)
            .where(Reminder.utc_ts <= current_time)
            .with_for_update(skip_locked=True)
        )
        reminders = session.execute(stmt).scalars().all()
        for reminder in reminders:
            if not reminder.correlation_id:
                reminder.correlation_id = str(uuid.uuid4())
            reminder.last_attempt_at = current_time
            scheduled_ids.append(reminder.id)
            deliver_reminder.apply_async(args=[str(reminder.id)], kwargs={"trace_id": reminder.correlation_id})
        session.flush()
        if owns_session:
            session.commit()
    finally:
        if owns_session:
            session.close()
    return scheduled_ids


@celery_app.task(bind=True, name="app.tasks.reminders.send_due_reminders")
def send_due_reminders(self, current_time_iso: Optional[str] = None) -> int:
    """Scan for due reminders and queue them for delivery."""

    current_time = _parse_time(current_time_iso)
    METRICS.set_gauge("worker_uptime_seconds", time.time())
    scheduled = schedule_due_reminders(current_time)
    if scheduled:
        logger.info("Queued %s reminders for delivery at %s.", len(scheduled), current_time.isoformat())
    return len(scheduled)


@celery_app.task(bind=True, name="app.tasks.reminders.deliver_reminder", max_retries=MAX_RETRIES)
def deliver_reminder(
    self,
    reminder_id: str,
    current_time_iso: Optional[str] = None,
    trace_id: Optional[str] = None,
) -> bool:
    """Deliver a single reminder and handle retry/backoff on failure."""

    now = _parse_time(current_time_iso)
    reminder_uuid = uuid.UUID(reminder_id)
    session = SessionLocal()
    reminder: Optional[Reminder] = None
    correlation_id: Optional[str] = trace_id

    try:
        reminder = session.get(Reminder, reminder_uuid)
        if reminder is None:
            correlation = correlation_id or str(uuid.uuid4())
            with correlation_scope(correlation):
                logger.warning("Reminder %s no longer exists.", reminder_id)
            return False

        correlation_id = reminder.correlation_id or correlation_id or str(uuid.uuid4())

        with correlation_scope(correlation_id):
            ensure_correlation_id(correlation_id)

            if reminder.status != ReminderStatusEnum.SCHEDULED:
                if reminder.status == ReminderStatusEnum.CANCELED:
                    log_reminder_event(
                        "reminder_canceled",
                        user_id=reminder.user_id,
                        reminder_id=reminder.id,
                        eta_utc=reminder.utc_ts,
                        status=reminder.status.value,
                    )
                    METRICS.increment_counter("reminder_canceled")
                elif reminder.status == ReminderStatusEnum.ERROR:
                    log_reminder_event(
                        "reminder_errored",
                        user_id=reminder.user_id,
                        reminder_id=reminder.id,
                        eta_utc=reminder.utc_ts,
                        status=reminder.status.value,
                        level="ERROR",
                    )
                logger.info(
                    "Reminder %s not scheduled (status=%s); skipping.", reminder.id, reminder.status.value
                )
                session.commit()
                return True

            target_ts = reminder.utc_ts or reminder.run_ts
            if target_ts and target_ts > now:
                wait_seconds = max(int((target_ts - now).total_seconds()), 60)
                session.commit()
                raise self.retry(countdown=wait_seconds)

            user = session.get(User, reminder.user_id)
            if user is None:
                raise RuntimeError(f"User {reminder.user_id} not found for reminder {reminder.id}")

            attempt_delivery(session, reminder, user, now)
            session.commit()
            logger.info("Reminder %s sent for user %s.", reminder.id, user.id)
            return True

    except self.MaxRetriesExceededError as exc:
        session.rollback()
        if reminder is not None:
            reminder.status = ReminderStatusEnum.ERROR
            reminder.last_attempt_at = now
            session.add(reminder)
        _record_failed_job(
            session,
            "deliver_reminder",
            {"reminder_id": reminder_id},
            str(exc),
            MAX_RETRIES,
        )
        session.commit()
        cid = correlation_id or (reminder.correlation_id if reminder else str(uuid.uuid4()))
        with correlation_scope(cid):
            log_reminder_event(
                "reminder_errored",
                user_id=reminder.user_id if reminder else None,
                reminder_id=reminder_uuid,
                eta_utc=reminder.utc_ts if reminder else None,
                status=ReminderStatusEnum.ERROR.value,
                level="ERROR",
                error=str(exc),
            )
            logger.error("Reminder %s failed after max retries: %s", reminder_id, exc)
            METRICS.increment_counter("reminder_error")
        return False

    except Exception as exc:
        session.rollback()
        attempts = self.request.retries + 1

        if reminder is not None:
            reminder.last_attempt_at = now
            session.add(reminder)

        cid = correlation_id or (reminder.correlation_id if reminder else str(uuid.uuid4()))

        if attempts >= MAX_RETRIES:
            if reminder is not None:
                reminder.status = ReminderStatusEnum.ERROR
            _record_failed_job(
                session,
                "deliver_reminder",
                {"reminder_id": reminder_id},
                str(exc),
                attempts,
            )
            session.commit()
            with correlation_scope(cid):
                log_reminder_event(
                    "reminder_errored",
                    user_id=reminder.user_id if reminder else None,
                    reminder_id=reminder_uuid,
                    eta_utc=reminder.utc_ts if reminder else None,
                    status=ReminderStatusEnum.ERROR.value,
                    level="ERROR",
                    error=str(exc),
                )
                logger.error("Reminder %s failed permanently: %s", reminder_id, exc)
                METRICS.increment_counter("reminder_error")
            return False

        session.commit()
        backoff = min(60 * (2 ** self.request.retries), 3600)
        with correlation_scope(cid):
            logger.warning(
                "Retrying reminder %s (attempt %s/%s) in %ss due to: %s",
                reminder_id,
                attempts,
                MAX_RETRIES,
                backoff,
                exc,
            )
        raise self.retry(exc=exc, countdown=backoff)

    finally:
        session.close()
