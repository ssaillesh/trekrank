"""Evaluate badge requirements against a user's current state and award new badges."""
import uuid
from collections import Counter

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models import (
    User, Trip, Badge, UserBadge, VisitedCountry, ActivityFeed,
)
from app.data.countries import continent_of, countries_in_continent

# Continents that count toward the "visit every continent" badge (Antarctica is
# excluded so the achievement stays attainable, but still has its own badge).
INHABITED_CONTINENTS = {"AF", "AS", "EU", "NA", "SA", "OC"}


def _visited_continents(db: Session, user: User) -> set[str]:
    """Continents the user has set foot on. The continent of their home country
    (where they reside) always counts, even without a logged trip there."""
    codes = db.execute(
        select(VisitedCountry.country_code).where(VisitedCountry.user_id == user.id)
    ).scalars().all()
    conts = {continent_of(c) for c in codes}
    if user.home_country:
        conts.add(continent_of(user.home_country))
    conts.discard(None)
    return conts


def _requirement_met(db: Session, user: User, req: dict) -> bool:
    rtype = req.get("type")

    if rtype == "continent_visited":
        return req["continent"] in _visited_continents(db, user)
    if rtype == "all_continents":
        return INHABITED_CONTINENTS.issubset(_visited_continents(db, user))

    if rtype == "trips":
        return user.total_trips >= req["threshold"]
    if rtype == "countries_visited":
        return user.total_countries >= req["threshold"]
    if rtype == "cities_visited":
        return user.total_cities >= req["threshold"]
    if rtype == "total_km":
        return float(user.total_km) >= req["threshold"]
    if rtype == "streak":
        return user.longest_streak >= req["threshold"]
    if rtype == "transport_mode":
        count = db.scalar(
            select(func.count()).select_from(Trip).where(
                Trip.user_id == user.id, Trip.transport_mode == req["mode"]
            )
        ) or 0
        return count >= req.get("count", 1)
    if rtype == "continent_complete":
        required = countries_in_continent(req["continent"])
        if not required:
            return False
        visited = set(
            db.execute(
                select(VisitedCountry.country_code).where(VisitedCountry.user_id == user.id)
            ).scalars().all()
        )
        return required.issubset(visited)
    if rtype == "trips_in_month":
        rows = db.execute(select(Trip.start_date).where(Trip.user_id == user.id)).scalars().all()
        counts = Counter((d.year, d.month) for d in rows if d)
        return any(c >= req["threshold"] for c in counts.values())
    return False


def evaluate_and_award(db: Session, user: User, trip_id: uuid.UUID | None = None) -> list[Badge]:
    """Award any newly-earned badges. Returns the list of badges just awarded."""
    earned_ids = set(
        db.execute(
            select(UserBadge.badge_id).where(UserBadge.user_id == user.id)
        ).scalars().all()
    )
    candidates = db.execute(
        select(Badge).where(Badge.id.notin_(earned_ids) if earned_ids else True)
    ).scalars().all()

    newly: list[Badge] = []
    for badge in candidates:
        if _requirement_met(db, user, badge.requirement):
            db.add(UserBadge(user_id=user.id, badge_id=badge.id, trip_id=trip_id))
            db.add(ActivityFeed(
                user_id=user.id,
                event_type="badge_earned",
                badge_id=badge.id,
                activity_metadata={"badge_name": badge.name},
            ))
            newly.append(badge)
    if newly:
        db.flush()
    return newly
