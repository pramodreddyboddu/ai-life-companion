"""add analytics metrics tables and persona tracking"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20241015_06"
down_revision = "20241015_05"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("current_persona_key", sa.String(length=64), nullable=True))

    op.create_table(
        "metrics_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_name", sa.String(length=64), nullable=False),
        sa.Column(
            "properties",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_metrics_events_event_name_created_at",
        "metrics_events",
        ["event_name", "created_at"],
    )
    op.create_index(
        "ix_metrics_events_user_event",
        "metrics_events",
        ["user_id", "event_name"],
    )

    op.create_table(
        "metrics_daily",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("metrics_date", sa.Date(), nullable=False),
        sa.Column("cohort_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("retained_day1", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("retained_day7", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("active_users", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("retention_rate_day1", sa.Float(), nullable=True),
        sa.Column("retention_rate_day7", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("metrics_date"),
    )


def downgrade() -> None:
    op.drop_index("ix_metrics_events_user_event", table_name="metrics_events")
    op.drop_index("ix_metrics_events_event_name_created_at", table_name="metrics_events")
    op.drop_table("metrics_daily")
    op.drop_table("metrics_events")
    op.drop_column("users", "current_persona_key")
