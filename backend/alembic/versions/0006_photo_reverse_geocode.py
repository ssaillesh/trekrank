"""add reverse-geocoded country/place to trip_photos

Revision ID: 0006_photo_reverse_geocode
Revises: 0005_photo_exif_location
Create Date: 2026-06-28
"""
from alembic import op
import sqlalchemy as sa

revision = "0006_photo_reverse_geocode"
down_revision = "0005_photo_exif_location"
branch_labels = None
depends_on = None


def _columns() -> dict:
    return {
        "captured_country": sa.Column("captured_country", sa.CHAR(length=2), nullable=True),
        "captured_place": sa.Column("captured_place", sa.String(length=120), nullable=True),
    }


def upgrade() -> None:
    # Idempotent: create_all() builds these on a fresh DB; add only what's missing.
    # trip_photos itself is gone from the models as of 0007, so a fresh DB never
    # creates it at all — skip.
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
