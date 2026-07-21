import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, Trip
from app.middleware.auth import get_current_user
from app.schemas.trip import (
    TripCreate, TripUpdate, TripOut, TripList, BackfillRequest, BackfillResponse,
)
from app.api.dispatch import enqueue_trip

router = APIRouter(prefix="/trips", tags=["trips"])


def _to_out(trip: Trip) -> TripOut:
    return TripOut(
        id=str(trip.id), user_id=str(trip.user_id), title=trip.title, notes=trip.notes,
        transport_mode=trip.transport_mode, origin_city=trip.origin_city,
        origin_country=trip.origin_country, dest_city=trip.dest_city,
        dest_country=trip.dest_country, start_date=trip.start_date, end_date=trip.end_date,
        distance_km=float(trip.distance_km) if trip.distance_km is not None else None,
        is_public=trip.is_public, status=trip.status, created_at=trip.created_at,
    )


def _owned_trip(db: Session, trip_id: str, user: User) -> Trip:
    try:
        tid = uuid.UUID(trip_id)
    except ValueError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Trip not found")
    trip = db.get(Trip, tid)
    if not trip or trip.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Trip not found")
    return trip


@router.post("", response_model=TripOut, status_code=201)
def create_trip(body: TripCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    trip = Trip(
        user_id=user.id, title=body.title, notes=body.notes,
        transport_mode=body.transport_mode, origin_city=body.origin_city,
        origin_country=body.origin_country, dest_city=body.dest_city,
        dest_country=body.dest_country.upper(), start_date=body.start_date,
        end_date=body.end_date, is_public=body.is_public, status="processing",
        origin_lat=body.origin_lat, origin_lng=body.origin_lng,
        dest_lat=body.dest_lat, dest_lng=body.dest_lng,
        distance_km=body.distance_km,
    )
    db.add(trip)
    db.commit()
    db.refresh(trip)
    enqueue_trip(str(trip.id))
    db.refresh(trip)
    return _to_out(trip)


@router.get("", response_model=TripList)
def list_trips(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    cursor: str | None = Query(default=None, description="ISO timestamp of last seen trip"),
    limit: int = Query(default=20, le=100),
):
    q = select(Trip).where(Trip.user_id == user.id)
    if cursor:
        try:
            q = q.where(Trip.created_at < datetime.fromisoformat(cursor))
        except ValueError:
            pass
    rows = db.execute(q.order_by(Trip.created_at.desc()).limit(limit + 1)).scalars().all()
    next_cursor = None
    if len(rows) > limit:
        next_cursor = rows[limit - 1].created_at.isoformat()
        rows = rows[:limit]
    return TripList(items=[_to_out(t) for t in rows], next_cursor=next_cursor)


@router.post("/backfill", response_model=BackfillResponse, status_code=201)
def backfill(body: BackfillRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    created_ids = []
    for t in body.trips:
        trip = Trip(
            user_id=user.id, title=t.title, transport_mode=t.transport_mode,
            origin_city=t.origin_city, origin_country=t.origin_country,
            dest_city=t.dest_city, dest_country=t.dest_country.upper(),
            start_date=t.start_date, end_date=t.end_date, status="processing",
        )
        db.add(trip)
        db.flush()
        created_ids.append(str(trip.id))
    db.commit()
    for tid in created_ids:
        enqueue_trip(tid)
    return BackfillResponse(
        created=len(created_ids), processing=True,
        message="Trips queued for geocoding and stat calculation",
    )


@router.get("/{trip_id}", response_model=TripOut)
def get_trip(trip_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _to_out(_owned_trip(db, trip_id, user))


@router.patch("/{trip_id}", response_model=TripOut)
def update_trip(trip_id: str, body: TripUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    trip = _owned_trip(db, trip_id, user)
    data = body.model_dump(exclude_unset=True)
    geo_changed = any(k in data for k in ("dest_city", "dest_country", "origin_city", "origin_country"))
    for field, value in data.items():
        if field == "dest_country" and value:
            value = value.upper()
        setattr(trip, field, value)
    if geo_changed:
        trip.status = "processing"
    db.add(trip)
    db.commit()
    db.refresh(trip)
    if geo_changed:
        enqueue_trip(str(trip.id))
        db.refresh(trip)
    return _to_out(trip)


@router.delete("/{trip_id}", status_code=204)
def delete_trip(trip_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    trip = _owned_trip(db, trip_id, user)
    db.delete(trip)
    db.commit()
    # Re-derive everything from the remaining trips so all values stay correct:
    # visited countries/cities, cached stat columns, then the Redis leaderboards.
    from app.services.stats import rebuild_visited_tables, recalculate_user_stats
    from app.services import leaderboard
    rebuild_visited_tables(db, user)
    recalculate_user_stats(db, user)
    db.commit()
    try:
        leaderboard.rebuild_for_user(db, user)
    except Exception:
        pass
