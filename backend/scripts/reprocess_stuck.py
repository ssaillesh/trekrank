"""Heal trips left in the 'processing' state.

A trip is created with status='processing' and finished asynchronously by the
Celery worker (geocode + distance + stats). If a trip was created while no
worker was running, it stays 'processing' forever. This script reprocesses
every such trip synchronously. It is idempotent for stuck trips (they never
completed) and runs on startup so deploys self-heal any backlog.
"""
from sqlalchemy import select

from app.database import SessionLocal
from app.models import Trip
from app.workers.trip_processor import process_trip_sync


def main() -> None:
    db = SessionLocal()
    try:
        ids = [
            str(tid)
            for tid in db.execute(
                select(Trip.id).where(Trip.status == "processing")
            ).scalars().all()
        ]
    finally:
        db.close()

    print(f"reprocess_stuck: {len(ids)} trip(s) to heal")
    for tid in ids:
        try:
            process_trip_sync(tid)
            print(f"  healed {tid}")
        except Exception as e:  # never let one bad trip block startup
            print(f"  failed {tid}: {e}")


if __name__ == "__main__":
    main()
