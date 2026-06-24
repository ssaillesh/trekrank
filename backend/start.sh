#!/usr/bin/env sh
# Production entrypoint: apply DB migrations and seed the badge catalog
# (both idempotent), then start the API. Railway injects $PORT.
set -e

echo "Running database migrations..."
alembic upgrade head

echo "Seeding badges..."
python -m scripts.seed_badges || echo "Badge seed skipped/failed (non-fatal)"

echo "Starting API on port ${PORT:-8000}..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
