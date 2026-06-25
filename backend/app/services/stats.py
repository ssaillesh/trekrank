"""User stat recalculation and detailed stat aggregation."""
from collections import defaultdict
from datetime import date

from sqlalchemy import select, func, delete
from sqlalchemy.orm import Session

from app.models import User, Trip, VisitedCountry, VisitedCity
from app.data.countries import continent_of, country_name


def compute_streak(trip_months: set[tuple[int, int]]) -> tuple[int, int]:
    """Given the set of (year, month) the user traveled, return (current_streak, longest_streak).

    A streak = consecutive calendar months each containing >= 1 trip.
    current_streak counts back from the most recent month the user traveled.
    """
    if not trip_months:
        return 0, 0
    months = sorted(trip_months)

    def prev_month(ym: tuple[int, int]) -> tuple[int, int]:
        y, m = ym
        return (y - 1, 12) if m == 1 else (y, m - 1)

    month_set = set(months)
    # longest
    longest = 0
    for ym in months:
        if prev_month(ym) not in month_set:  # start of a run
            length = 1
            cur = ym

            def next_month(x):
                y, m = x
                return (y + 1, 1) if m == 12 else (y, m + 1)

            while next_month(cur) in month_set:
                cur = next_month(cur)
                length += 1
            longest = max(longest, length)

    # current: from latest traveled month going backwards
    current = 1
    cur = months[-1]
    while prev_month(cur) in month_set:
        cur = prev_month(cur)
        current += 1
    return current, longest


def rebuild_visited_tables(db: Session, user: User) -> None:
    """Recompute visited_countries / visited_cities from scratch based on the
    user's CURRENT trips. Needed after deleting a trip so the visit counts and
    country/city totals stay accurate (the per-trip upsert only increments)."""
    db.execute(delete(VisitedCountry).where(VisitedCountry.user_id == user.id))
    db.execute(delete(VisitedCity).where(VisitedCity.user_id == user.id))

    trips = db.execute(select(Trip).where(Trip.user_id == user.id)).scalars().all()
    countries: dict[str, dict] = {}
    cities: dict[tuple[str, str], dict] = {}
    for t in trips:
        c = countries.setdefault(t.dest_country, {"first": t.start_date, "count": 0})
        c["count"] += 1
        c["first"] = min(c["first"], t.start_date)

        ckey = (t.dest_city, t.dest_country)
        ci = cities.setdefault(ckey, {"first": t.start_date, "count": 0,
                                      "lat": t.dest_lat, "lng": t.dest_lng})
        ci["count"] += 1
        ci["first"] = min(ci["first"], t.start_date)
        if ci["lat"] is None and t.dest_lat is not None:
            ci["lat"], ci["lng"] = t.dest_lat, t.dest_lng

    for code, v in countries.items():
        db.add(VisitedCountry(user_id=user.id, country_code=code,
                              country_name=country_name(code),
                              first_visited=v["first"], visit_count=v["count"]))
    for (city, code), v in cities.items():
        vc = VisitedCity(user_id=user.id, city_name=city, country_code=code,
                         first_visited=v["first"], visit_count=v["count"])
        vc.lat, vc.lng = v["lat"], v["lng"]
        db.add(vc)
    db.flush()


def recalculate_user_stats(db: Session, user: User) -> None:
    """Recompute and persist the user's cached stat columns from source tables."""
    total_countries = db.scalar(
        select(func.count()).select_from(VisitedCountry).where(VisitedCountry.user_id == user.id)
    ) or 0
    total_cities = db.scalar(
        select(func.count()).select_from(VisitedCity).where(VisitedCity.user_id == user.id)
    ) or 0
    total_trips = db.scalar(
        select(func.count()).select_from(Trip).where(Trip.user_id == user.id)
    ) or 0
    total_km = db.scalar(
        select(func.coalesce(func.sum(Trip.distance_km), 0)).where(Trip.user_id == user.id)
    ) or 0

    months = db.execute(
        select(Trip.start_date).where(Trip.user_id == user.id)
    ).scalars().all()
    trip_months = {(d.year, d.month) for d in months if d}
    current_streak, longest_streak = compute_streak(trip_months)

    user.total_countries = int(total_countries)
    user.total_cities = int(total_cities)
    user.total_trips = int(total_trips)
    user.total_km = float(total_km)
    user.current_streak = current_streak
    # Recompute fresh from the user's current trips so deletions update it too.
    user.longest_streak = longest_streak
    db.add(user)
    db.flush()


def detailed_stats(db: Session, user: User) -> dict:
    """Build the payload for GET /users/:username/stats."""
    visited = db.execute(
        select(VisitedCountry).where(VisitedCountry.user_id == user.id)
    ).scalars().all()

    continents = sorted({c for vc in visited if (c := continent_of(vc.country_code))})

    top_country = None
    if visited:
        top = max(visited, key=lambda v: v.visit_count)
        top_country = {"code": top.country_code, "visits": top.visit_count}

    # transport breakdown
    transport_rows = db.execute(
        select(Trip.transport_mode, func.count())
        .where(Trip.user_id == user.id, Trip.transport_mode.isnot(None))
        .group_by(Trip.transport_mode)
    ).all()
    transport_breakdown = {mode: int(count) for mode, count in transport_rows}

    # per-year stats
    trips = db.execute(select(Trip).where(Trip.user_id == user.id)).scalars().all()
    by_year: dict[int, dict] = defaultdict(lambda: {"countries": set(), "cities": set(), "km": 0.0})
    for t in trips:
        y = t.start_date.year
        by_year[y]["countries"].add(t.dest_country)
        by_year[y]["cities"].add((t.dest_city, t.dest_country))
        by_year[y]["km"] += float(t.distance_km or 0)

    year_stats = {
        str(y): {
            "countries": len(v["countries"]),
            "cities": len(v["cities"]),
            "km": round(v["km"], 2),
        }
        for y, v in sorted(by_year.items(), reverse=True)
    }

    return {
        "user_id": str(user.id),
        "total_countries": user.total_countries,
        "total_cities": user.total_cities,
        "total_km": float(user.total_km),
        "total_trips": user.total_trips,
        "current_streak": user.current_streak,
        "longest_streak": user.longest_streak,
        "continents_visited": continents,
        "top_country": top_country,
        "transport_breakdown": transport_breakdown,
        "year_stats": year_stats,
    }
