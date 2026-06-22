"""Worker 1: Trip Processor.

Geocode origin/destination, compute distance via PostGIS, update the trip,
maintain visited_countries/visited_cities, recompute user stats, rebuild
Redis leaderboards, insert an activity-feed entry, then evaluate badges.
"""
import uuid

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Trip, User, VisitedCountry, VisitedCity
from app.data.countries import country_name
from app.services.geocoding import geocode
from app.services.distance import distance_km_postgis
from app.services.stats import recalculate_user_stats
from app.services import leaderboard
from app.models import ActivityFeed
from app.workers.celery_app import celery


def _set_point(db: Session, table: str, row_id, lat: float, lng: float, column: str) -> None:
    """Persist a lat/lng as a PostGIS GEOGRAPHY(POINT, 4326)."""
    db.execute(
        text(
            f"UPDATE {table} SET {column} = ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography "
            f"WHERE id = :id"
        ),
        {"lng": lng, "lat": lat, "id": row_id},
    )


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
        db.add(new_city)
        db.flush()
        if dest_latlng:
            _set_point(db, "visited_cities", new_city.id, dest_latlng[0], dest_latlng[1], "coords")
    db.flush()


def process_trip_sync(trip_id: str) -> None:
    """Synchronous pipeline (also used directly by tests)."""
    db: Session = SessionLocal()
    try:
        trip = db.get(Trip, uuid.UUID(str(trip_id)))
        if not trip:
            return
        user = db.get(User, trip.user_id)

        # 1. Geocode
        dest = geocode(trip.dest_city, trip.dest_country)
        origin = geocode(trip.origin_city, trip.origin_country) if trip.origin_city else None
        if not origin and user and user.home_city:
            origin = geocode(user.home_city, user.home_country)

        # 2/3. Coordinates (PostGIS geography) + distance via ST_Distance
        trip.status = "done"
        db.add(trip)
        db.flush()
        if dest:
            _set_point(db, "trips", trip.id, dest[0], dest[1], "dest_coords")
        if origin:
            _set_point(db, "trips", trip.id, origin[0], origin[1], "origin_coords")
        if origin and dest:
            trip.distance_km = distance_km_postgis(db, origin[0], origin[1], dest[0], dest[1])
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
