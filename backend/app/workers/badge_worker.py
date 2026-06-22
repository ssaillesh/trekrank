"""Worker 2: Badge Evaluator. Awards newly-earned badges after trip processing."""
import uuid

from app.database import SessionLocal
from app.models import User
from app.services.badge_evaluator import evaluate_and_award
from app.workers.celery_app import celery


def evaluate_badges_sync(user_id: str, trip_id: str | None = None) -> list[str]:
    db = SessionLocal()
    try:
        user = db.get(User, uuid.UUID(str(user_id)))
        if not user:
            return []
        tid = uuid.UUID(str(trip_id)) if trip_id else None
        awarded = evaluate_and_award(db, user, tid)
        db.commit()
        # 5. (push notification would fire here for each new badge)
        return [b.id for b in awarded]
    finally:
        db.close()


@celery.task(name="trekrank.evaluate_badges")
def evaluate_badges(user_id: str, trip_id: str | None = None) -> list[str]:
    return evaluate_badges_sync(user_id, trip_id)
