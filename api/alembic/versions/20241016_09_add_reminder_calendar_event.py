"""Add calendar_event_id to reminders."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20241016_09_add_reminder_calendar_event"
down_revision = "20241016_08_add_memory_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("reminders", sa.Column("calendar_event_id", sa.String(length=128), nullable=True))


def downgrade() -> None:
    op.drop_column("reminders", "calendar_event_id")
