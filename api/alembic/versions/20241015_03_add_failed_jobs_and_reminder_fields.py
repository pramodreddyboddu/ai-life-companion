"""add failed jobs table and reminder metadata"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20241015_03"
down_revision = "20241015_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("push_token", sa.String(length=255), nullable=True))
    op.add_column("reminders", sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("reminders", sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "failed_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("job_name", sa.String(length=128), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("last_error_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
            server_onupdate=sa.text("now()"),
        ),
    )


def downgrade() -> None:
    op.drop_table("failed_jobs")
    op.drop_column("reminders", "sent_at")
    op.drop_column("reminders", "last_attempt_at")
    op.drop_column("users", "push_token")
