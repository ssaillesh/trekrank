"""Seed the badges catalog (idempotent + declarative).

The BADGES list is the source of truth: badges in it are upserted, and any badge
in the DB that is no longer listed is removed along with its references.
"""
from sqlalchemy import select, delete

from app.database import SessionLocal
from app.models import Badge, UserBadge, ActivityFeed

# (id, name, description, category, emoji, requirement)
BADGES = [
    ("first_trip", "First Steps", "Log your first trip", "milestone", "🗺️", {"type": "trips", "threshold": 1}),
    ("five_countries", "Explorer", "Visit 5 countries", "milestone", "🌎", {"type": "countries_visited", "threshold": 5}),
    ("ten_countries", "Globetrotter", "Visit 10 countries", "milestone", "🌍", {"type": "countries_visited", "threshold": 10}),
    ("twenty_five", "World Traveler", "Visit 25 countries", "milestone", "🏆", {"type": "countries_visited", "threshold": 25}),
    ("fifty_countries", "Legendary Explorer", "Visit 50 countries", "milestone", "👑", {"type": "countries_visited", "threshold": 50}),
    ("ten_cities", "City Hopper", "Visit 10 different cities", "milestone", "🏙️", {"type": "cities_visited", "threshold": 10}),
    ("fifty_cities", "Urban Legend", "Visit 50 different cities", "milestone", "🌆", {"type": "cities_visited", "threshold": 50}),
    ("ten_k_km", "10K Club", "Travel 10,000 km total", "milestone", "🎖️", {"type": "total_km", "threshold": 10000}),
    ("fifty_k_km", "Around the World", "Travel 50,000 km (Earth circumference)", "milestone", "🌐", {"type": "total_km", "threshold": 50000}),
    ("north_america", "North America", "Visit all NA countries", "continent", "🗽", {"type": "continent_complete", "continent": "NA"}),
    ("europe", "Eurotrip", "Visit all EU countries", "continent", "🗼", {"type": "continent_complete", "continent": "EU"}),
    ("asia", "Eastern Explorer", "Visit all Asian countries", "continent", "🏯", {"type": "continent_complete", "continent": "AS"}),
    ("first_flight", "Takeoff", "Log your first flight", "transport", "✈️", {"type": "transport_mode", "mode": "flight", "count": 1}),
    ("train_lover", "Rail Rider", "Take 10 train trips", "transport", "🚆", {"type": "transport_mode", "mode": "train", "count": 10}),
    ("road_warrior", "Road Warrior", "Take 10 car trips", "transport", "🚗", {"type": "transport_mode", "mode": "car", "count": 10}),
    ("weekend_warrior", "Weekend Warrior", "Log 3 trips in one month", "special", "🎒", {"type": "trips_in_month", "threshold": 3}),
    # Per-continent "set foot here" badges. The continent the user resides in
    # (their home country) always counts as visited.
    ("visited_af", "Out of Africa", "Set foot in Africa", "continent", "🦁", {"type": "continent_visited", "continent": "AF"}),
    ("visited_as", "Asia Bound", "Set foot in Asia", "continent", "🐘", {"type": "continent_visited", "continent": "AS"}),
    ("visited_eu", "Old World", "Set foot in Europe", "continent", "🏰", {"type": "continent_visited", "continent": "EU"}),
    ("visited_na", "North Star", "Set foot in North America", "continent", "🦅", {"type": "continent_visited", "continent": "NA"}),
    ("visited_sa", "Amazonian", "Set foot in South America", "continent", "🦜", {"type": "continent_visited", "continent": "SA"}),
    ("visited_oc", "Down Under", "Set foot in Oceania", "continent", "🦘", {"type": "continent_visited", "continent": "OC"}),
    ("visited_an", "Polar Pioneer", "Set foot in Antarctica", "continent", "🐧", {"type": "continent_visited", "continent": "AN"}),
    ("all_continents", "Worldwide", "Visit every inhabited continent", "continent", "🌏", {"type": "all_continents"}),
]


def seed() -> tuple[int, int]:
    db = SessionLocal()
    try:
        catalog_ids = {b[0] for b in BADGES}
        n = 0
        for bid, name, desc, cat, emoji, req in BADGES:
            existing = db.get(Badge, bid)
            if existing:
                existing.name, existing.description, existing.category = name, desc, cat
                existing.emoji, existing.requirement = emoji, req
            else:
                db.add(Badge(id=bid, name=name, description=desc, category=cat,
                             emoji=emoji, requirement=req))
                n += 1

        # Remove badges no longer in the catalog, plus any awards / feed entries
        # that referenced them (UserBadge has no cascade, so delete it first).
        stale = [bid for bid in db.execute(select(Badge.id)).scalars().all()
                 if bid not in catalog_ids]
        if stale:
            db.execute(delete(UserBadge).where(UserBadge.badge_id.in_(stale)))
            db.execute(delete(ActivityFeed).where(ActivityFeed.badge_id.in_(stale)))
            db.execute(delete(Badge).where(Badge.id.in_(stale)))

        db.commit()
        return n, len(stale)
    finally:
        db.close()


if __name__ == "__main__":
    added, removed = seed()
    print(f"Seeded badges. {added} new, {removed} removed, {len(BADGES)} total.")
