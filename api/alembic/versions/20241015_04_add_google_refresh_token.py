"""add google refresh token column"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20241015_04"
down_revision = "20241015_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("google_refresh_token", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "google_refresh_token")
