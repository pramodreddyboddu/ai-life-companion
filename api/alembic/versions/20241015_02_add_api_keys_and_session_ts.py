"""add api keys table and session timestamps"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20241015_02"
down_revision = "20241015_01"
branch_labels = None
depends_on = None


api_key_status_enum = postgresql.ENUM("active", "revoked", name="api_key_status_enum", create_type=False)


def upgrade() -> None:
    op.execute(
        "DO $$ BEGIN "
        "CREATE TYPE api_key_status_enum AS ENUM ('active', 'revoked'); "
        "EXCEPTION WHEN duplicate_object THEN NULL; END $$;"
    )

    op.create_table(
        "api_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("prefix", sa.String(length=16), nullable=False),
        sa.Column("key_hash", sa.String(length=128), nullable=False),
        sa.Column(
            "status",
            api_key_status_enum,
            nullable=False,
            server_default="active",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("prefix", name="uq_api_keys_prefix"),
    )
    op.create_index("ix_api_keys_user_id", "api_keys", ["user_id"])

    op.add_column(
        "sessions",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )


def downgrade() -> None:
    op.drop_column("sessions", "created_at")
    op.drop_index("ix_api_keys_user_id", table_name="api_keys")
    op.drop_table("api_keys")
    op.execute("DROP TYPE IF EXISTS api_key_status_enum CASCADE;")
