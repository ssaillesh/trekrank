from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, Badge, UserBadge
from app.middleware.auth import get_current_user
from app.schemas.social import BadgeOut

router = APIRouter(prefix="/badges", tags=["badges"])


@router.get("", response_model=list[BadgeOut])
def list_badges(db: Session = Depends(get_db)):
    badges = db.execute(select(Badge).order_by(Badge.category, Badge.id)).scalars().all()
    return [
        BadgeOut(id=b.id, name=b.name, description=b.description, icon_url=b.icon_url,
                 category=b.category, requirement=b.requirement)
        for b in badges
    ]


@router.get("/me", response_model=list[BadgeOut])
def my_badges(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    earned = {
        ub.badge_id: ub
        for ub in db.execute(select(UserBadge).where(UserBadge.user_id == user.id)).scalars().all()
    }
    badges = db.execute(select(Badge)).scalars().all()
    return [
        BadgeOut(id=b.id, name=b.name, description=b.description, icon_url=b.icon_url,
                 category=b.category, requirement=b.requirement,
                 earned=b.id in earned,
                 earned_at=earned[b.id].earned_at if b.id in earned else None)
        for b in badges
    ]


@router.get("/{badge_id}", response_model=BadgeOut)
def badge_detail(badge_id: str, db: Session = Depends(get_db)):
    b = db.get(Badge, badge_id)
    if not b:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Badge not found")
    earned_count = db.scalar(
        select(func.count()).select_from(UserBadge).where(UserBadge.badge_id == b.id)
    ) or 0
    return BadgeOut(id=b.id, name=b.name, description=b.description, icon_url=b.icon_url,
                    category=b.category, requirement={**b.requirement, "earned_by": int(earned_count)})
