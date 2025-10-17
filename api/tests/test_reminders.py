from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from zoneinfo import ZoneInfo

from app.db.models import PlanEnum, Reminder, ReminderStatusEnum, User
from app.settings import settings
from app.tasks import reminders as reminder_tasks


@pytest.mark.usefixtures("apply_migrations")
def test_schedule_and_deliver_reminder_triggers_notifications(db_session, monkeypatch) -> None:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    user = User(id=uuid.uuid4(), email="reminder@example.com", plan=PlanEnum.FREE, push_token="ExpoPushToken[test]")
    db_session.add(user)

    run_ts = now + timedelta(minutes=2)
    reminder = Reminder(
        id=uuid.uuid4(),
        user_id=user.id,
        text="Drink a glass of water.",
        run_ts=run_ts,
        original_phrase="in 2 minutes",
        local_ts=run_ts.astimezone(ZoneInfo("America/Chicago")),
        utc_ts=run_ts,
        correlation_id=str(uuid.uuid4()),
    )
    db_session.add(reminder)
    db_session.flush()

    monkeypatch.setattr(settings, "resend_api_key", "test-resend")
    monkeypatch.setattr(settings, "resend_from_email", "noreply@example.com")
    monkeypatch.setattr(settings, "expo_access_token", "test-expo-token")

    target_time = now + timedelta(minutes=3)

    with patch("app.tasks.reminders.send_email_notification", return_value=True) as email_mock, \
        patch("app.tasks.reminders.send_push_notification", return_value=True) as push_mock, \
        patch("app.tasks.reminders.deliver_reminder.apply_async") as apply_mock:

        def _immediate_dispatch(*, args=None, kwargs=None):
            reminder_uuid = uuid.UUID(args[0])
            reminder_obj = db_session.get(Reminder, reminder_uuid)
            reminder_tasks.attempt_delivery(db_session, reminder_obj, user, target_time)
            db_session.flush()

        apply_mock.side_effect = _immediate_dispatch
        reminder_tasks.schedule_due_reminders(target_time, session=db_session)

    db_session.refresh(reminder)
    assert reminder.status == ReminderStatusEnum.SENT
    assert reminder.sent_at is not None
    assert email_mock.called
    assert push_mock.called
