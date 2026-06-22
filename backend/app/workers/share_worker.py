"""Worker 4: Share Card Generator. Renders a 1080x1920 PNG and returns its URL."""
import uuid

from app.database import SessionLocal
from app.models import User
from app.services.share_card import generate_share_card
from app.workers.celery_app import celery


def generate_share_card_sync(user_id: str, card_type: str, year: int | None) -> str | None:
    db = SessionLocal()
    try:
        user = db.get(User, uuid.UUID(str(user_id)))
        if not user:
            return None
        return generate_share_card(db, user, card_type, year)
    finally:
        db.close()


@celery.task(name="trekrank.generate_share_card")
def generate_share_card_task(user_id: str, card_type: str, year: int | None) -> str | None:
    return generate_share_card_sync(user_id, card_type, year)
