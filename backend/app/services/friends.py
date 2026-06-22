"""Friend-graph helpers."""
import uuid

from sqlalchemy import select, or_, and_
from sqlalchemy.orm import Session

from app.models import Friendship


def friend_ids(db: Session, user_id: uuid.UUID) -> list[uuid.UUID]:
    """All accepted friends of a user (other side of the friendship)."""
    rows = db.execute(
        select(Friendship).where(
            Friendship.status == "accepted",
            or_(Friendship.requester_id == user_id, Friendship.addressee_id == user_id),
        )
    ).scalars().all()
    out = []
    for f in rows:
        out.append(f.addressee_id if f.requester_id == user_id else f.requester_id)
    return out


def are_friends(db: Session, a: uuid.UUID, b: uuid.UUID) -> bool:
    return db.scalar(
        select(Friendship.id).where(
            Friendship.status == "accepted",
            or_(
                and_(Friendship.requester_id == a, Friendship.addressee_id == b),
                and_(Friendship.requester_id == b, Friendship.addressee_id == a),
            ),
        )
    ) is not None
