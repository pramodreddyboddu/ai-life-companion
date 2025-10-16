"""create core domain tables with vector support"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20241015_01"
down_revision = None
branch_labels = None
depends_on = None


plan_enum = postgresql.ENUM("free", "pro", name="plan_enum", create_type=False)
memory_type_enum = postgresql.ENUM(
    "note", "goal", "habit", "preference", "contact", name="memory_type_enum", create_type=False
)
task_status_enum = postgresql.ENUM("pending", "done", name="task_status_enum", create_type=False)
reminder_status_enum = postgresql.ENUM(
    "scheduled", "sent", "failed", name="reminder_status_enum", create_type=False
)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    op.execute(
        "DO $$ BEGIN "
        "CREATE TYPE plan_enum AS ENUM ('free', 'pro'); "
        "EXCEPTION WHEN duplicate_object THEN NULL; END $$;"
    )
    op.execute(
        "DO $$ BEGIN "
        "CREATE TYPE memory_type_enum AS ENUM ('note', 'goal', 'habit', 'preference', 'contact'); "
        "EXCEPTION WHEN duplicate_object THEN NULL; END $$;"
    )
    op.execute(
        "DO $$ BEGIN "
        "CREATE TYPE task_status_enum AS ENUM ('pending', 'done'); "
        "EXCEPTION WHEN duplicate_object THEN NULL; END $$;"
    )
    op.execute(
        "DO $$ BEGIN "
        "CREATE TYPE reminder_status_enum AS ENUM ('scheduled', 'sent', 'failed'); "
        "EXCEPTION WHEN duplicate_object THEN NULL; END $$;"
    )

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False, unique=True),
        sa.Column("plan", plan_enum, nullable=False, server_default=sa.text("'free'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "personas",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("key", sa.String(length=64), nullable=False, unique=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=False),
    )

    op.create_table(
        "habits",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("cadence", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("streak", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("last_check_ts", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )

    op.create_table(
        "memories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("type", memory_type_enum, nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(1536), nullable=False),
        sa.Column("source", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )

    op.create_table(
        "reminders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("run_ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", reminder_status_enum, nullable=False, server_default=sa.text("'scheduled'")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )

    op.create_table(
        "sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("transcript", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("tokens_used", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )

    op.create_table(
        "tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("due_ts", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", task_status_enum, nullable=False, server_default=sa.text("'pending'")),
        sa.Column("linked_calendar_event_id", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )

    op.create_index("ix_habits_user_id", "habits", ["user_id"])
    op.create_index("ix_memories_user_id", "memories", ["user_id"])
    op.create_index("ix_reminders_user_id", "reminders", ["user_id"])
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])
    op.create_index("ix_tasks_user_id", "tasks", ["user_id"])

    op.create_index("ix_habits_cadence_gin", "habits", ["cadence"], postgresql_using="gin")
    op.create_index("ix_sessions_transcript_gin", "sessions", ["transcript"], postgresql_using="gin")

    op.execute(
        "CREATE INDEX idx_memories_embedding_ivfflat "
        "ON memories USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_memories_embedding_ivfflat;")

    op.drop_index("ix_sessions_transcript_gin", table_name="sessions")
    op.drop_index("ix_habits_cadence_gin", table_name="habits")
    op.drop_index("ix_tasks_user_id", table_name="tasks")
    op.drop_index("ix_sessions_user_id", table_name="sessions")
    op.drop_index("ix_reminders_user_id", table_name="reminders")
    op.drop_index("ix_memories_user_id", table_name="memories")
    op.drop_index("ix_habits_user_id", table_name="habits")

    op.drop_table("tasks")
    op.drop_table("sessions")
    op.drop_table("reminders")
    op.drop_table("memories")
    op.drop_table("habits")
    op.drop_table("personas")
    op.drop_table("users")

    op.execute("DROP TYPE IF EXISTS reminder_status_enum CASCADE;")
    op.execute("DROP TYPE IF EXISTS task_status_enum CASCADE;")
    op.execute("DROP TYPE IF EXISTS memory_type_enum CASCADE;")
    op.execute("DROP TYPE IF EXISTS plan_enum CASCADE;")
