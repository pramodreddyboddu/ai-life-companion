"""ORM models for core application entities."""

from __future__ import annotations

import uuid
from enum import Enum
from typing import Any, Dict, List, Optional

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


UUID_PK = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB


class PlanEnum(str, Enum):
    FREE = "free"
    PRO = "pro"


class MemoryTypeEnum(str, Enum):
    NOTE = "note"
    GOAL = "goal"
    HABIT = "habit"
    PREFERENCE = "preference"
    CONTACT = "contact"


class TaskStatusEnum(str, Enum):
    PENDING = "pending"
    DONE = "done"


class ReminderStatusEnum(str, Enum):
    SCHEDULED = "scheduled"
    SENT = "sent"
    FAILED = "failed"


class ApiKeyStatusEnum(str, Enum):
    ACTIVE = "active"
    REVOKED = "revoked"


_values = lambda enum_cls: [member.value for member in enum_cls]

plan_enum = postgresql.ENUM(
    PlanEnum, name="plan_enum", create_type=False, values_callable=_values
)
memory_type_enum = postgresql.ENUM(
    MemoryTypeEnum, name="memory_type_enum", create_type=False, values_callable=_values
)
task_status_enum = postgresql.ENUM(
    TaskStatusEnum, name="task_status_enum", create_type=False, values_callable=_values
)
reminder_status_enum = postgresql.ENUM(
    ReminderStatusEnum, name="reminder_status_enum", create_type=False, values_callable=_values
)
api_key_status_enum = postgresql.ENUM(
    ApiKeyStatusEnum, name="api_key_status_enum", create_type=False, values_callable=_values
)


class User(Base):
    """User of the AI companion."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID_PK, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(sa.String(255), unique=True, nullable=False)
    plan: Mapped[PlanEnum] = mapped_column(plan_enum, nullable=False, server_default=PlanEnum.FREE.value)
    push_token: Mapped[Optional[str]] = mapped_column(sa.String(255))
    google_refresh_token: Mapped[Optional[str]] = mapped_column(sa.Text)
    stripe_customer_id: Mapped[Optional[str]] = mapped_column(sa.String(64))
    stripe_subscription_id: Mapped[Optional[str]] = mapped_column(sa.String(64))
    current_persona_key: Mapped[Optional[str]] = mapped_column(sa.String(64))
    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )

    memories: Mapped[List["Memory"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    tasks: Mapped[List["Task"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    habits: Mapped[List["Habit"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    reminders: Mapped[List["Reminder"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    sessions: Mapped[List["Session"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    api_keys: Mapped[List["ApiKey"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Memory(Base):
    """Structured memory derived from user interactions."""

    __tablename__ = "memories"

    id: Mapped[uuid.UUID] = mapped_column(UUID_PK, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    type: Mapped[MemoryTypeEnum] = mapped_column(memory_type_enum, nullable=False)
    text: Mapped[str] = mapped_column(sa.Text, nullable=False)
    embedding: Mapped[List[float]] = mapped_column(Vector(1536), nullable=False)
    source: Mapped[Optional[str]] = mapped_column(sa.String(255))
    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )

    user: Mapped["User"] = relationship(back_populates="memories")


class Task(Base):
    """Actionable task generated for the user."""

    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(UUID_PK, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    due_ts: Mapped[Optional[sa.DateTime]] = mapped_column(sa.DateTime(timezone=True))
    status: Mapped[TaskStatusEnum] = mapped_column(
        task_status_enum, nullable=False, server_default=TaskStatusEnum.PENDING.value
    )
    linked_calendar_event_id: Mapped[Optional[str]] = mapped_column(sa.String(255))

    user: Mapped["User"] = relationship(back_populates="tasks")


class Habit(Base):
    """Recurring habit tracked for the user."""

    __tablename__ = "habits"

    id: Mapped[uuid.UUID] = mapped_column(UUID_PK, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    cadence: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    streak: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default="0")
    last_check_ts: Mapped[Optional[sa.DateTime]] = mapped_column(sa.DateTime(timezone=True))

    user: Mapped["User"] = relationship(back_populates="habits")


class Reminder(Base):
    """Reminder message to be sent to the user."""

    __tablename__ = "reminders"

    id: Mapped[uuid.UUID] = mapped_column(UUID_PK, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    text: Mapped[str] = mapped_column(sa.Text, nullable=False)
    run_ts: Mapped[sa.DateTime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    status: Mapped[ReminderStatusEnum] = mapped_column(
        reminder_status_enum, nullable=False, server_default=ReminderStatusEnum.SCHEDULED.value
    )
    last_attempt_at: Mapped[Optional[sa.DateTime]] = mapped_column(sa.DateTime(timezone=True))
    sent_at: Mapped[Optional[sa.DateTime]] = mapped_column(sa.DateTime(timezone=True))

    user: Mapped["User"] = relationship(back_populates="reminders")


class Persona(Base):
    """Available AI personas."""

    __tablename__ = "personas"

    id: Mapped[uuid.UUID] = mapped_column(UUID_PK, primary_key=True, default=uuid.uuid4)
    key: Mapped[str] = mapped_column(sa.String(64), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    system_prompt: Mapped[str] = mapped_column(sa.Text, nullable=False)


class Session(Base):
    """Conversation session with aggregated transcript."""

    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID_PK, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    transcript: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    tokens_used: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default="0")
    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )

    user: Mapped["User"] = relationship(back_populates="sessions")


class ApiKey(Base):
    """API keys used for authenticating requests."""

    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = mapped_column(UUID_PK, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    prefix: Mapped[str] = mapped_column(sa.String(16), nullable=False, unique=True)
    key_hash: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    status: Mapped[ApiKeyStatusEnum] = mapped_column(
        api_key_status_enum, nullable=False, server_default=ApiKeyStatusEnum.ACTIVE.value
    )
    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
    updated_at: Mapped[sa.DateTime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
    )

    user: Mapped["User"] = relationship(back_populates="api_keys")


class FailedJob(Base):
    """Dead-letter log entry for failed background tasks."""

    __tablename__ = "failed_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID_PK, primary_key=True, default=uuid.uuid4)
    job_name: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    payload: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    error_message: Mapped[str] = mapped_column(sa.Text, nullable=False)
    attempts: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    last_error_at: Mapped[sa.DateTime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
    updated_at: Mapped[sa.DateTime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
    )


class MetricsEvent(Base):
    """Immutable event stream for custom analytics."""

    __tablename__ = "metrics_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID_PK, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    event_name: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    properties: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )


class MetricsDaily(Base):
    """Daily aggregated retention metrics."""

    __tablename__ = "metrics_daily"

    id: Mapped[uuid.UUID] = mapped_column(UUID_PK, primary_key=True, default=uuid.uuid4)
    metrics_date: Mapped[sa.Date] = mapped_column(sa.Date, nullable=False, unique=True)
    cohort_size: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default="0")
    retained_day1: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default="0")
    retained_day7: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default="0")
    active_users: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default="0")
    retention_rate_day1: Mapped[Optional[float]] = mapped_column(sa.Float)
    retention_rate_day7: Mapped[Optional[float]] = mapped_column(sa.Float)
    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
    updated_at: Mapped[sa.DateTime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
    )


__all__ = [
    "Base",
    "Habit",
    "Memory",
    "Persona",
    "Reminder",
    "Session",
    "FailedJob",
    "ApiKey",
    "Task",
    "User",
    "PlanEnum",
    "MemoryTypeEnum",
    "TaskStatusEnum",
    "ReminderStatusEnum",
    "ApiKeyStatusEnum",
    "MetricsEvent",
    "MetricsDaily",
]
