#!/usr/bin/env sh
# Production entrypoint: apply DB migrations + seed badges (idempotent), heal any
# trips stuck in "processing", start the background worker, then start the API.
# A single Railway service runs both the API and the Celery worker, so trips are
# actually processed (geocoding + distance) instead of queuing forever.
set -e

echo "Running database migrations..."
alembic upgrade head

echo "Seeding badges..."
python -m scripts.seed_badges || echo "Badge seed skipped/failed (non-fatal)"

echo "Healing any trips stuck in 'processing'..."
python -m scripts.reprocess_stuck || echo "Reprocess skipped/failed (non-fatal)"

echo "Starting Celery worker (background)..."
celery -A app.workers worker -l info -c 2 &

echo "Starting API on port ${PORT:-8000}..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
