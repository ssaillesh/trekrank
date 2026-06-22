"""Helper to enqueue Celery tasks, with a synchronous fallback.

If the broker is unreachable (no worker / no Redis), we run the job inline so the
app still works end-to-end in a minimal dev setup.
"""
from app.workers.trip_processor import process_trip, process_trip_sync
from app.workers.photo_worker import process_photo, process_photo_sync
from app.workers.share_worker import generate_share_card_task, generate_share_card_sync


def enqueue_trip(trip_id: str) -> None:
    try:
        process_trip.delay(trip_id)
    except Exception:
        process_trip_sync(trip_id)


def enqueue_photo(photo_id: str) -> None:
    try:
        process_photo.delay(photo_id)
    except Exception:
        process_photo_sync(photo_id)


def run_share_card(user_id: str, card_type: str, year: int | None) -> str | None:
    """Share cards are awaited synchronously so we can return the URL immediately."""
    return generate_share_card_sync(user_id, card_type, year)
