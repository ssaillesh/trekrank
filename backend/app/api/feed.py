from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, ActivityFeed, Trip, Badge
from app.middleware.auth import get_current_user
from app.schemas.social import (
    FeedResponse, FeedItem, FeedTrip, FeedBadge, FeedRecommendation, RecommendationCreate,
)
from app.schemas.user import UserPublic
from app.services.friends import friend_ids

router = APIRouter(prefix="/feed", tags=["feed"])


def _render(db: Session, rows, users_cache: dict) -> list[FeedItem]:
    items = []
    for af in rows:
        u = users_cache.get(af.user_id) or db.get(User, af.user_id)
        users_cache[af.user_id] = u
        if not u:
            continue
        item = FeedItem(
            id=str(af.id), event_type=af.event_type,
            user=UserPublic(id=str(u.id), username=u.username, display_name=u.display_name,
                            avatar_url=u.avatar_url),
            created_at=af.created_at,
        )
        if af.trip_id:
            trip = db.get(Trip, af.trip_id)
            if trip:
                item.trip = FeedTrip(
                    id=str(trip.id), title=trip.title, dest_city=trip.dest_city,
                    dest_country=trip.dest_country,
                    distance_km=float(trip.distance_km) if trip.distance_km else None,
                )
                if trip.photos:
                    item.photo_url = trip.photos[0].thumbnail_url or trip.photos[0].photo_url
        if af.badge_id:
            badge = db.get(Badge, af.badge_id)
            if badge:
                item.badge = FeedBadge(id=badge.id, name=badge.name, icon_url=badge.icon_url)
        if af.event_type == "recommendation" and af.activity_metadata:
            md = af.activity_metadata
            item.recommendation = FeedRecommendation(
                text=md.get("text", ""), city=md.get("city"), country=md.get("country"))
        items.append(item)
    return items


def _paginate(db: Session, user_ids, cursor: str | None, limit: int) -> FeedResponse:
    if not user_ids:
        return FeedResponse(items=[], next_cursor=None)
    q = select(ActivityFeed).where(ActivityFeed.user_id.in_(user_ids))
    if cursor:
        try:
            q = q.where(ActivityFeed.created_at < datetime.fromisoformat(cursor))
        except ValueError:
            pass
    rows = db.execute(q.order_by(ActivityFeed.created_at.desc()).limit(limit + 1)).scalars().all()
    next_cursor = None
    if len(rows) > limit:
        next_cursor = rows[limit - 1].created_at.isoformat()
        rows = rows[:limit]
    return FeedResponse(items=_render(db, rows, {}), next_cursor=next_cursor)


@router.get("", response_model=FeedResponse)
def friends_feed(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, le=50),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Home feed = the user's own activity (their trips + earned badges) plus
    # their friends', newest first — so achievements show up on their own feed.
    ids = friend_ids(db, user.id) + [user.id]
    return _paginate(db, ids, cursor, limit)


@router.post("/recommend", response_model=FeedItem, status_code=201)
def create_recommendation(
    body: RecommendationCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Post a spot recommendation to the feed."""
    af = ActivityFeed(
        user_id=user.id, event_type="recommendation",
        activity_metadata={"text": body.text, "city": body.city, "country": body.country},
    )
    db.add(af)
    db.commit()
    db.refresh(af)
    return _render(db, [af], {})[0]


@router.get("/me", response_model=FeedResponse)
def my_feed(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, le=50),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _paginate(db, [user.id], cursor, limit)
