"""initial schema: enable extensions + create all tables (incl. PostGIS geography)

Revision ID: 0001_init
Revises:
Create Date: 2026-06-22
"""
from alembic import op
import sqlalchemy as sa

from app.database import Base
import app.models  # noqa: F401  (populate metadata)

revision = "0001_init"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    # PostGIS is the production datastore (see docker-compose's postgis image).
    # It is optional for the portable/native runtime: only enable it when the
    # extension is actually available, so a vanilla PostgreSQL still migrates.
    postgis_available = bind.execute(
        sa.text("SELECT 1 FROM pg_available_extensions WHERE name = 'postgis'")
    ).scalar()
    if postgis_available:
        op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
