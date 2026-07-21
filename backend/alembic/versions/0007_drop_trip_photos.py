"""drop trip_photos (photo upload / map-pin feature removed)

Revision ID: 0007_drop_trip_photos
Revises: 0006_photo_reverse_geocode
Create Date: 2026-07-20
"""
from alembic import op
import sqlalchemy as sa

revision = "0007_drop_trip_photos"
down_revision = "0006_photo_reverse_geocode"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Idempotent: safe to run even if the table was never created.
    bind = op.get_bind()
    if "trip_photos" in sa.inspect(bind).get_table_names():
        op.drop_table("trip_photos")


def downgrade() -> None:
    op.create_table(
        "trip_photos",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("trip_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("trips.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("user_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("photo_url", sa.String(500), nullable=False),
        sa.Column("thumbnail_url", sa.String(500), nullable=True),
        sa.Column("caption", sa.String(300), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("captured_lat", sa.Float(), nullable=True),
        sa.Column("captured_lng", sa.Float(), nullable=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("location_source", sa.String(10), nullable=True),
        sa.Column("captured_country", sa.CHAR(2), nullable=True),
        sa.Column("captured_place", sa.String(120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
