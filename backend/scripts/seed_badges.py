"""Seed the badges catalog (idempotent)."""
from app.database import SessionLocal
from app.models import Badge

BADGES = [
    ("first_trip", "First Steps", "Log your first trip", "milestone", {"type": "trips", "threshold": 1}),
    ("five_countries", "Explorer", "Visit 5 countries", "milestone", {"type": "countries_visited", "threshold": 5}),
    ("ten_countries", "Globetrotter", "Visit 10 countries", "milestone", {"type": "countries_visited", "threshold": 10}),
    ("twenty_five", "World Traveler", "Visit 25 countries", "milestone", {"type": "countries_visited", "threshold": 25}),
    ("fifty_countries", "Legendary Explorer", "Visit 50 countries", "milestone", {"type": "countries_visited", "threshold": 50}),
    ("ten_cities", "City Hopper", "Visit 10 different cities", "milestone", {"type": "cities_visited", "threshold": 10}),
    ("fifty_cities", "Urban Legend", "Visit 50 different cities", "milestone", {"type": "cities_visited", "threshold": 50}),
    ("ten_k_km", "10K Club", "Travel 10,000 km total", "milestone", {"type": "total_km", "threshold": 10000}),
    ("fifty_k_km", "Around the World", "Travel 50,000 km (Earth circumference)", "milestone", {"type": "total_km", "threshold": 50000}),
    ("streak_3", "Momentum", "Travel 3 months in a row", "streak", {"type": "streak", "threshold": 3}),
    ("streak_6", "Unstoppable", "Travel 6 months in a row", "streak", {"type": "streak", "threshold": 6}),
    ("streak_12", "Nomad", "Travel every month for a year", "streak", {"type": "streak", "threshold": 12}),
    ("north_america", "North America", "Visit all NA countries", "continent", {"type": "continent_complete", "continent": "NA"}),
    ("europe", "Eurotrip", "Visit all EU countries", "continent", {"type": "continent_complete", "continent": "EU"}),
    ("asia", "Eastern Explorer", "Visit all Asian countries", "continent", {"type": "continent_complete", "continent": "AS"}),
    ("first_flight", "Takeoff", "Log your first flight", "transport", {"type": "transport_mode", "mode": "flight", "count": 1}),
    ("train_lover", "Rail Rider", "Take 10 train trips", "transport", {"type": "transport_mode", "mode": "train", "count": 10}),
    ("road_warrior", "Road Warrior", "Take 10 car trips", "transport", {"type": "transport_mode", "mode": "car", "count": 10}),
    ("weekend_warrior", "Weekend Warrior", "Log 3 trips in one month", "special", {"type": "trips_in_month", "threshold": 3}),
    ("photographer", "Shutterbug", "Upload 50 trip photos", "special", {"type": "photos_uploaded", "threshold": 50}),
]


def seed() -> int:
    db = SessionLocal()
    try:
        n = 0
        for bid, name, desc, cat, req in BADGES:
            existing = db.get(Badge, bid)
            if existing:
                existing.name, existing.description, existing.category, existing.requirement = name, desc, cat, req
            else:
                db.add(Badge(id=bid, name=name, description=desc, category=cat, requirement=req))
                n += 1
        db.commit()
        return n
    finally:
        db.close()


if __name__ == "__main__":
    added = seed()
    print(f"Seeded badges. {added} new, {len(BADGES)} total.")
