"""add users.featured_badges

Revision ID: 0004_featured_badges
Revises: 0003_waitlist
Create Date: 2026-06-25
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0004_featured_badges"
down_revision = "0003_waitlist"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Idempotent: 0001's create_all() already adds this column on a fresh DB.
    bind = op.get_bind()
    cols = [c["name"] for c in sa.inspect(bind).get_columns("users")]
    if "featured_badges" not in cols:
        op.add_column(
            "users",
            sa.Column("featured_badges", JSONB, nullable=False, server_default="[]"),
        )


def downgrade() -> None:
    op.drop_column("users", "featured_badges")
