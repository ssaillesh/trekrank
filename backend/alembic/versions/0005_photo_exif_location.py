"""add proof-of-travel EXIF columns to trip_photos

Revision ID: 0005_photo_exif_location
Revises: 0004_featured_badges
Create Date: 2026-06-28
"""
from alembic import op
import sqlalchemy as sa

revision = "0005_photo_exif_location"
down_revision = "0004_featured_badges"
branch_labels = None
depends_on = None

def _columns() -> dict:
    # Built fresh per call so a Column object is never reused across op.add_column.
    return {
        "captured_lat": sa.Column("captured_lat", sa.Float(), nullable=True),
        "captured_lng": sa.Column("captured_lng", sa.Float(), nullable=True),
        "captured_at": sa.Column("captured_at", sa.DateTime(timezone=True), nullable=True),
        "location_source": sa.Column("location_source", sa.String(length=10), nullable=True),
    }


def upgrade() -> None:
    # Idempotent: 0001's create_all() builds these on a fresh DB, so only add the
    # ones that are missing (older DBs get them here). trip_photos itself is gone
    # from the models as of 0007, so a fresh DB never creates it at all — skip.
    bind = op.get_bind()
    if "trip_photos" not in sa.inspect(bind).get_table_names():
        return
    existing = {c["name"] for c in sa.inspect(bind).get_columns("trip_photos")}
    for name, column in _columns().items():
        if name not in existing:
            op.add_column("trip_photos", column)


def downgrade() -> None:
    for name in _columns():
        op.drop_column("trip_photos", name)
