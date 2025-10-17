"""Add index for memory search."""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "20241016_08_add_memory_index"
down_revision = "20241016_07_add_reminder_audit_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_memories_user_id_created_at ON memories (user_id, created_at DESC)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_memories_user_id_created_at")
