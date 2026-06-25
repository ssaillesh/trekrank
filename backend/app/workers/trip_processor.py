"""Worker 1: Trip Processor.

Geocode origin/destination, compute distance via PostGIS, update the trip,
maintain visited_countries/visited_cities, recompute user stats, rebuild
Redis leaderboards, insert an activity-feed entry, then evaluate badges.
"""
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Trip, User, VisitedCountry, VisitedCity
from app.data.countries import country_name
from app.services.geocoding import geocode
from app.services.distance import distance_km
from app.services.stats import recalculate_user_stats
from app.services import leaderboard
from app.models import ActivityFeed
from app.workers.celery_app import celery


def _upsert_visited(db: Session, trip: Trip, dest_latlng: tuple[float, float] | None) -> None:
    # country
    vc = db.execute(
        select(VisitedCountry).where(
            VisitedCountry.user_id == trip.user_id,
            VisitedCountry.country_code == trip.dest_country,
        )
    ).scalar_one_or_none()
    if vc:
        vc.visit_count += 1
        if trip.start_date < vc.first_visited:
            vc.first_visited = trip.start_date
    else:
        db.add(VisitedCountry(
            user_id=trip.user_id,
            country_code=trip.dest_country,
            country_name=country_name(trip.dest_country),
            first_visited=trip.start_date,
            visit_count=1,
        ))

    # city
    city = db.execute(
        select(VisitedCity).where(
            VisitedCity.user_id == trip.user_id,
            VisitedCity.city_name == trip.dest_city,
            VisitedCity.country_code == trip.dest_country,
        )
    ).scalar_one_or_none()
    if city:
        city.visit_count += 1
        if trip.start_date < city.first_visited:
            city.first_visited = trip.start_date
    else:
        new_city = VisitedCity(
            user_id=trip.user_id,
            city_name=trip.dest_city,
            country_code=trip.dest_country,
            first_visited=trip.start_date,
            visit_count=1,
        )
        if dest_latlng:
            new_city.lat, new_city.lng = dest_latlng[0], dest_latlng[1]
        db.add(new_city)
        db.flush()
    db.flush()


def process_trip_sync(trip_id: str) -> None:
    """Synchronous pipeline (also used directly by tests)."""
    db: Session = SessionLocal()
    try:
        trip = db.get(Trip, uuid.UUID(str(trip_id)))
        if not trip:
            return
        user = db.get(User, trip.user_id)

        # 1. Resolve coordinates. Prefer client-supplied coords (the iOS app
        #    geocodes on-device and sends them) so we can skip the slow, rate-
        #    limited Nominatim call entirely. Fall back to geocoding otherwise.
        if trip.dest_lat is not None and trip.dest_lng is not None:
            dest = (trip.dest_lat, trip.dest_lng)
        else:
            dest = geocode(trip.dest_city, trip.dest_country)

        if trip.origin_lat is not None and trip.origin_lng is not None:
            origin = (trip.origin_lat, trip.origin_lng)
        elif trip.origin_city:
            origin = geocode(trip.origin_city, trip.origin_country)
        else:
            origin = None
        if not origin and user and user.home_city:
            origin = geocode(user.home_city, user.home_country)

        # 2/3. Coordinates (plain lat/lng) + distance via Haversine
        trip.status = "done"
        if dest:
            trip.dest_lat, trip.dest_lng = dest[0], dest[1]
        if origin:
            trip.origin_lat, trip.origin_lng = origin[0], origin[1]
        # Keep a client-supplied distance (e.g. a recorded GPS route); otherwise
        # compute straight-line distance between origin and destination.
        if origin and dest and trip.distance_km is None:
            trip.distance_km = distance_km(origin[0], origin[1], dest[0], dest[1])
        db.add(trip)
        db.flush()

        # 4. Visited tables
        _upsert_visited(db, trip, dest)

        # 5. Recalculate user stats
        recalculate_user_stats(db, user)

        # 7. Activity feed entry
        db.add(ActivityFeed(
            user_id=user.id,
            event_type="new_trip",
            trip_id=trip.id,
            activity_metadata={
                "city": trip.dest_city,
                "country": trip.dest_country,
                "distance_km": float(trip.distance_km) if trip.distance_km else None,
            },
        ))
        db.commit()

        # 6. Rebuild Redis leaderboards for this user's friend group
        try:
            leaderboard.rebuild_for_user(db, user)
        except Exception:
            pass

        # 8. Badge evaluation
        from app.workers.badge_worker import evaluate_badges_sync
        evaluate_badges_sync(str(user.id), str(trip.id))
    finally:
        db.close()


@celery.task(name="trekrank.process_trip")
def process_trip(trip_id: str) -> None:
    process_trip_sync(trip_id)
