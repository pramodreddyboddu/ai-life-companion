"""Add audit fields to reminders and extend status enum."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20241016_07_add_reminder_audit_fields"
down_revision = "20241015_06_add_metrics_tables"
branch_labels = None
depends_on = None


REMINDER_STATUS_OLD = ("scheduled", "sent", "failed")
REMINDER_STATUS_NEW = ("scheduled", "sent", "canceled", "error")


def upgrade() -> None:
    op.add_column("reminders", sa.Column("original_phrase", sa.Text(), nullable=True))
    op.add_column("reminders", sa.Column("local_ts", sa.DateTime(timezone=True), nullable=True))
    op.add_column("reminders", sa.Column("utc_ts", sa.DateTime(timezone=True), nullable=True))
    op.add_column("reminders", sa.Column("correlation_id", sa.String(length=64), nullable=True))

    new_enum = sa.Enum(*REMINDER_STATUS_NEW, name="reminder_status_enum_new")
    new_enum.create(op.get_bind())

    op.execute("ALTER TABLE reminders ALTER COLUMN status DROP DEFAULT")
    op.execute(
        """
        ALTER TABLE reminders
        ALTER COLUMN status TYPE reminder_status_enum_new
        USING (
            CASE
                WHEN status = 'failed' THEN 'error'::reminder_status_enum_new
                ELSE status::text::reminder_status_enum_new
            END
        )
        """
    )
    op.execute("ALTER TABLE reminders ALTER COLUMN status SET DEFAULT 'scheduled'")

    op.execute("UPDATE reminders SET utc_ts = run_ts WHERE utc_ts IS NULL")
    op.execute("UPDATE reminders SET local_ts = run_ts WHERE local_ts IS NULL")
    op.execute("UPDATE reminders SET correlation_id = id::text WHERE correlation_id IS NULL")
    op.alter_column("reminders", "utc_ts", nullable=False, existing_type=sa.DateTime(timezone=True))
    op.alter_column("reminders", "local_ts", nullable=False, existing_type=sa.DateTime(timezone=True))
    op.alter_column("reminders", "correlation_id", nullable=False, existing_type=sa.String(length=64))

    op.execute("DROP TYPE reminder_status_enum")
    op.execute("ALTER TYPE reminder_status_enum_new RENAME TO reminder_status_enum")


def downgrade() -> None:
    old_enum = sa.Enum(*REMINDER_STATUS_OLD, name="reminder_status_enum_old")
    old_enum.create(op.get_bind())

    op.execute("ALTER TABLE reminders ALTER COLUMN status DROP DEFAULT")
    op.execute(
        """
        ALTER TABLE reminders
        ALTER COLUMN status TYPE reminder_status_enum_old
        USING (
            CASE
                WHEN status = 'error' THEN 'failed'::reminder_status_enum_old
                WHEN status = 'canceled' THEN 'failed'::reminder_status_enum_old
                ELSE status::text::reminder_status_enum_old
            END
        )
        """
    )
    op.execute("ALTER TABLE reminders ALTER COLUMN status SET DEFAULT 'scheduled'")

    op.execute("DROP TYPE reminder_status_enum")
    op.execute("ALTER TYPE reminder_status_enum_old RENAME TO reminder_status_enum")

    op.drop_column("reminders", "correlation_id")
    op.drop_column("reminders", "utc_ts")
    op.drop_column("reminders", "local_ts")
    op.drop_column("reminders", "original_phrase")
