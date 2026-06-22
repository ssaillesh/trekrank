import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, Challenge, ChallengeParticipant
from app.middleware.auth import get_current_user
from app.schemas.social import ChallengeCreate, ChallengeOut, ChallengeParticipantOut
from app.schemas.user import UserPublic

router = APIRouter(prefix="/challenges", tags=["challenges"])


def _metric_value(user: User, ctype: str) -> int:
    return {
        "countries": user.total_countries,
        "cities": user.total_cities,
        "km": int(float(user.total_km)),
        "trips": user.total_trips,
    }.get(ctype, 0)


def _to_out(db: Session, ch: Challenge, me: User | None) -> ChallengeOut:
    parts = db.execute(
        select(ChallengeParticipant).where(ChallengeParticipant.challenge_id == ch.id)
    ).scalars().all()
    p_out = []
    my_progress = None
    for p in parts:
        u = db.get(User, p.user_id)
        if not u:
            continue
        p_out.append(ChallengeParticipantOut(
            user=UserPublic(id=str(u.id), username=u.username, display_name=u.display_name,
                            avatar_url=u.avatar_url),
            progress=p.progress, completed=p.completed,
        ))
        if me and p.user_id == me.id:
            my_progress = p.progress
    p_out.sort(key=lambda x: x.progress, reverse=True)
    return ChallengeOut(
        id=str(ch.id), title=ch.title, description=ch.description,
        challenge_type=ch.challenge_type, target_value=ch.target_value,
        start_date=ch.start_date.isoformat(), end_date=ch.end_date.isoformat(),
        is_global=ch.is_global, participants=p_out, my_progress=my_progress,
    )


@router.get("", response_model=list[ChallengeOut])
def list_challenges(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    today = date.today()
    rows = db.execute(
        select(Challenge).where(Challenge.end_date >= today).order_by(Challenge.start_date)
    ).scalars().all()
    return [_to_out(db, ch, user) for ch in rows]


@router.post("", response_model=ChallengeOut, status_code=201)
def create_challenge(body: ChallengeCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if body.challenge_type not in ("countries", "cities", "km", "trips"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid challenge_type")
    ch = Challenge(
        title=body.title, description=body.description, challenge_type=body.challenge_type,
        target_value=body.target_value, start_date=date.fromisoformat(body.start_date),
        end_date=date.fromisoformat(body.end_date), is_global=False, created_by=user.id,
    )
    db.add(ch)
    db.flush()
    # creator joins automatically
    db.add(ChallengeParticipant(challenge_id=ch.id, user_id=user.id,
                                progress=_metric_value(user, ch.challenge_type)))
    # invite usernames
    for uname in body.invite_usernames:
        target = db.scalar(select(User).where(User.username == uname))
        if target and target.id != user.id:
            db.add(ChallengeParticipant(challenge_id=ch.id, user_id=target.id,
                                        progress=_metric_value(target, ch.challenge_type)))
    db.commit()
    db.refresh(ch)
    return _to_out(db, ch, user)


@router.post("/{challenge_id}/join", response_model=ChallengeOut)
def join_challenge(challenge_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        cid = uuid.UUID(challenge_id)
    except ValueError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Challenge not found")
    ch = db.get(Challenge, cid)
    if not ch:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Challenge not found")
    existing = db.scalar(
        select(ChallengeParticipant).where(
            ChallengeParticipant.challenge_id == cid, ChallengeParticipant.user_id == user.id
        )
    )
    if not existing:
        db.add(ChallengeParticipant(challenge_id=cid, user_id=user.id,
                                    progress=_metric_value(user, ch.challenge_type)))
        db.commit()
    db.refresh(ch)
    return _to_out(db, ch, user)


@router.get("/{challenge_id}", response_model=ChallengeOut)
def challenge_detail(challenge_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        cid = uuid.UUID(challenge_id)
    except ValueError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Challenge not found")
    ch = db.get(Challenge, cid)
    if not ch:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Challenge not found")
    return _to_out(db, ch, user)
