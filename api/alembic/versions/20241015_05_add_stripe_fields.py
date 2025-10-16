"""add stripe fields to user"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20241015_05"
down_revision = "20241015_04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("stripe_customer_id", sa.String(length=64), nullable=True))
    op.add_column("users", sa.Column("stripe_subscription_id", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "stripe_subscription_id")
    op.drop_column("users", "stripe_customer_id")
