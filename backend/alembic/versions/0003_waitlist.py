"""add waitlist_signups table

Revision ID: 0003_waitlist
Revises: 0002_badge_emoji
Create Date: 2026-06-25
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0003_waitlist"
down_revision = "0002_badge_emoji"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Idempotent: 0001's create_all() already builds this table on a fresh DB,
    # so only create it when missing (older DBs still get it here).
    bind = op.get_bind()
    if "waitlist_signups" not in sa.inspect(bind).get_table_names():
        op.create_table(
            "waitlist_signups",
            sa.Column("id", UUID(as_uuid=True), primary_key=True),
            sa.Column("email", sa.String(length=255), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=True),
            sa.Column("desired_username", sa.String(length=60), nullable=True),
            sa.Column("source", sa.String(length=60), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_waitlist_signups_email", "waitlist_signups", ["email"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_waitlist_signups_email", table_name="waitlist_signups")
    op.drop_table("waitlist_signups")
