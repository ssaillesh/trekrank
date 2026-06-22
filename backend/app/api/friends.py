import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, or_, and_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, Friendship
from app.middleware.auth import get_current_user
from app.schemas.social import FriendRequestCreate, FriendshipOut, FriendOut
from app.schemas.user import UserPublic
from app.services.friends import friend_ids

router = APIRouter(prefix="/friends", tags=["friends"])


def _pub(u: User) -> UserPublic:
    return UserPublic(id=str(u.id), username=u.username, display_name=u.display_name,
                      avatar_url=u.avatar_url, bio=u.bio)


@router.get("", response_model=list[FriendOut])
def list_friends(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.execute(
        select(Friendship).where(
            Friendship.status == "accepted",
            or_(Friendship.requester_id == user.id, Friendship.addressee_id == user.id),
        )
    ).scalars().all()
    out = []
    for f in rows:
        other_id = f.addressee_id if f.requester_id == user.id else f.requester_id
        other = db.get(User, other_id)
        if other:
            out.append(FriendOut(friendship_id=str(f.id), user=_pub(other),
                                 status=f.status, since=f.updated_at))
    return out


@router.post("/request", response_model=FriendshipOut, status_code=201)
def send_request(body: FriendRequestCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    target = db.scalar(select(User).where(User.username == body.username))
    if not target:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    if target.id == user.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot friend yourself")
    existing = db.scalar(
        select(Friendship).where(
            or_(
                and_(Friendship.requester_id == user.id, Friendship.addressee_id == target.id),
                and_(Friendship.requester_id == target.id, Friendship.addressee_id == user.id),
            )
        )
    )
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Friendship already {existing.status}")
    f = Friendship(requester_id=user.id, addressee_id=target.id, status="pending")
    db.add(f)
    db.commit()
    db.refresh(f)
    return FriendshipOut(friendship_id=str(f.id), status=f.status, addressee=_pub(target))


@router.get("/requests", response_model=list[FriendshipOut])
def pending_requests(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.execute(
        select(Friendship).where(
            Friendship.addressee_id == user.id, Friendship.status == "pending"
        )
    ).scalars().all()
    out = []
    for f in rows:
        requester = db.get(User, f.requester_id)
        out.append(FriendshipOut(friendship_id=str(f.id), status=f.status,
                                 requester=_pub(requester) if requester else None))
    return out


def _get_friendship(db: Session, fid: str) -> Friendship:
    try:
        f = db.get(Friendship, uuid.UUID(fid))
    except ValueError:
        f = None
    if not f:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Friendship not found")
    return f


@router.post("/accept/{friendship_id}", response_model=FriendshipOut)
def accept(friendship_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    f = _get_friendship(db, friendship_id)
    if f.addressee_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your request to accept")
    f.status = "accepted"
    db.commit()
    requester = db.get(User, f.requester_id)
    return FriendshipOut(friendship_id=str(f.id), status=f.status,
                         requester=_pub(requester) if requester else None)


@router.post("/reject/{friendship_id}", status_code=204)
def reject(friendship_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    f = _get_friendship(db, friendship_id)
    if f.addressee_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your request to reject")
    db.delete(f)
    db.commit()


@router.delete("/{friendship_id}", status_code=204)
def remove_friend(friendship_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    f = _get_friendship(db, friendship_id)
    if user.id not in (f.requester_id, f.addressee_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your friendship")
    db.delete(f)
    db.commit()


@router.get("/suggestions", response_model=list[UserPublic])
def suggestions(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Friends-of-friends not already connected to the user."""
    my_friends = set(friend_ids(db, user.id))
    suggestion_scores: dict[uuid.UUID, int] = {}
    for fid in my_friends:
        for fof in friend_ids(db, fid):
            if fof != user.id and fof not in my_friends:
                suggestion_scores[fof] = suggestion_scores.get(fof, 0) + 1
    ordered = sorted(suggestion_scores.items(), key=lambda kv: kv[1], reverse=True)[:10]
    out = []
    for uid, _ in ordered:
        u = db.get(User, uid)
        if u:
            out.append(_pub(u))
    return out
