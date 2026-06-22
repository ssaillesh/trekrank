"""Redis sorted-set leaderboards for friend groups, with DB fallback computation.

Key pattern: leaderboard:{metric}:{period}:friends:{user_id}  (ZSET of friend_id -> value)
TTL of 5 minutes; rebuilt by the trip-processor worker whenever a trip changes.
"""
import uuid
from datetime import date

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models import User, Trip, VisitedCountry, VisitedCity
from app.redis_client import redis_client
from app.config import settings
from app.services.friends import friend_ids

VALID_METRICS = {"countries", "cities", "km", "trips"}


def _key(metric: str, period: str, user_id: uuid.UUID) -> str:
    return f"leaderboard:{metric}:{period}:friends:{user_id}"


def _period_bounds(period: str) -> tuple[date | None, date | None]:
    """Return (start, end_exclusive) for a period, or (None, None) for all_time."""
    if period == "all_time":
        return None, None
    if period == "month":
        today = date.today()
        start = date(today.year, today.month, 1)
        end = date(today.year + 1, 1, 1) if today.month == 12 else date(today.year, today.month + 1, 1)
        return start, end
    # assume a 4-digit year
    try:
        y = int(period)
        return date(y, 1, 1), date(y + 1, 1, 1)
    except ValueError:
        return None, None


def _metric_value(db: Session, user: User, metric: str, period: str) -> float:
    start, end = _period_bounds(period)

    if period == "all_time":
        if metric == "countries":
            return float(user.total_countries)
        if metric == "cities":
            return float(user.total_cities)
        if metric == "km":
            return float(user.total_km)
        if metric == "trips":
            return float(user.total_trips)

    # period-scoped: compute from trips in range
    q = select(Trip).where(Trip.user_id == user.id)
    if start:
        q = q.where(Trip.start_date >= start, Trip.start_date < end)
    trips = db.execute(q).scalars().all()

    if metric == "countries":
        return float(len({t.dest_country for t in trips}))
    if metric == "cities":
        return float(len({(t.dest_city, t.dest_country) for t in trips}))
    if metric == "km":
        return float(sum(float(t.distance_km or 0) for t in trips))
    if metric == "trips":
        return float(len(trips))
    return 0.0


def rebuild_for_user(db: Session, user: User) -> None:
    """Rebuild all friend-leaderboard ZSETs that include `user` (self + each friend's group)."""
    fids = friend_ids(db, user.id)
    group_user_ids = set(fids) | {user.id}
    members = db.execute(select(User).where(User.id.in_(group_user_ids))).scalars().all()

    # For each member's perspective, the group is their own friends + themselves.
    # MVP simplification: rebuild the requesting user's own group here; each member's
    # own group is rebuilt when their own trips change.
    for metric in VALID_METRICS:
        for period in ("all_time", "month", str(date.today().year)):
            key = _key(metric, period, user.id)
            pipe = redis_client.pipeline()
            pipe.delete(key)
            for m in members:
                pipe.zadd(key, {str(m.id): _metric_value(db, m, metric, period)})
            pipe.expire(key, settings.leaderboard_ttl_seconds)
            pipe.execute()


def get_rankings(db: Session, user: User, metric: str, period: str) -> dict:
    """Return ranked friend leaderboard. Rebuilds the ZSET on cache miss."""
    key = _key(metric, period, user.id)
    if not redis_client.exists(key):
        rebuild_for_user(db, user)

    raw = redis_client.zrevrange(key, 0, -1, withscores=True)
    if not raw:
        # No friends / empty: just rank the user alone.
        raw = [(str(user.id), _metric_value(db, user, metric, period))]

    member_ids = [uuid.UUID(uid) for uid, _ in raw]
    users = {
        u.id: u
        for u in db.execute(select(User).where(User.id.in_(member_ids))).scalars().all()
    }

    rankings = []
    my_rank = None
    for i, (uid, score) in enumerate(raw, start=1):
        u = users.get(uuid.UUID(uid))
        if not u:
            continue
        if u.id == user.id:
            my_rank = i
        rankings.append({
            "rank": i,
            "user": {
                "id": str(u.id), "username": u.username, "display_name": u.display_name,
                "avatar_url": u.avatar_url,
            },
            "value": score,
            "trend": "same",
        })
    return {"metric": metric, "period": period, "rankings": rankings, "my_rank": my_rank}


def rebuild_global(db: Session, metric: str = "countries", limit: int = 100) -> None:
    """Hourly cron rebuilds the global leaderboard ZSET from cached user stats."""
    col = {
        "countries": User.total_countries,
        "cities": User.total_cities,
        "km": User.total_km,
        "trips": User.total_trips,
    }[metric]
    rows = db.execute(select(User).order_by(col.desc()).limit(limit)).scalars().all()
    key = f"leaderboard:{metric}:all_time:global"
    pipe = redis_client.pipeline()
    pipe.delete(key)
    for u in rows:
        pipe.zadd(key, {str(u.id): float(getattr(u, {
            "countries": "total_countries", "cities": "total_cities",
            "km": "total_km", "trips": "total_trips"}[metric]))})
    pipe.expire(key, 3600)
    pipe.execute()


def get_global(db: Session, metric: str, limit: int = 100) -> dict:
    key = f"leaderboard:{metric}:all_time:global"
    if not redis_client.exists(key):
        rebuild_global(db, metric, limit)
    raw = redis_client.zrevrange(key, 0, limit - 1, withscores=True)
    member_ids = [uuid.UUID(uid) for uid, _ in raw]
    users = {
        u.id: u for u in db.execute(select(User).where(User.id.in_(member_ids))).scalars().all()
    }
    rankings = []
    for i, (uid, score) in enumerate(raw, start=1):
        u = users.get(uuid.UUID(uid))
        if not u:
            continue
        rankings.append({
            "rank": i,
            "user": {"id": str(u.id), "username": u.username, "display_name": u.display_name,
                     "avatar_url": u.avatar_url},
            "value": score,
            "trend": "same",
        })
    return {"metric": metric, "period": "all_time", "rankings": rankings, "my_rank": None}
