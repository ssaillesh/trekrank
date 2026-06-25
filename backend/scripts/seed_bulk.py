"""Seed 100 uniquely-named test users with varied trips so the GLOBAL Ranks
board is competitive (a real spread of countries / cities / km / trips).

Run:  python -m scripts.seed_bulk
Idempotent: skips usernames that already exist. All accounts use password
TrekDemo123!.
"""
import random

from sqlalchemy import select

from app.database import SessionLocal
from app.models import User, Trip
from app.services.security import hash_password
from app.services.stats import recalculate_user_stats
from app.services import leaderboard
from app.workers.trip_processor import process_trip_sync

PASSWORD = "TrekDemo123!"
COUNT = 100

FIRST = ["Ava", "Noah", "Mia", "Liam", "Zoe", "Ethan", "Aria", "Leo", "Maya", "Kai",
         "Nina", "Omar", "Lena", "Ravi", "Sara", "Theo", "Ivy", "Hugo", "Elsa", "Jude",
         "Tara", "Marco", "Yuki", "Diego", "Anya", "Felix", "Chloe", "Amir", "Rosa", "Finn"]
LAST = ["Stone", "Vega", "Frost", "Knox", "Reyes", "Wilde", "Cruz", "Nash", "Lang", "Bauer",
        "Okafor", "Sato", "Costa", "Haas", "Kova", "Mori", "Singh", "Larsen", "Romero", "Quinn",
        "Adler", "Bose", "Dahl", "Engel", "Falk", "Greco", "Hale", "Ito", "Jansen", "Kaur"]

# (city, country, lat, lng)
CITIES = [
    ("Paris", "FR", 48.8566, 2.3522), ("London", "GB", 51.5074, -0.1278),
    ("Rome", "IT", 41.9028, 12.4964), ("Berlin", "DE", 52.52, 13.405),
    ("Madrid", "ES", 40.4168, -3.7038), ("Lisbon", "PT", 38.7223, -9.1393),
    ("Amsterdam", "NL", 52.3676, 4.9041), ("Vienna", "AT", 48.2082, 16.3738),
    ("Athens", "GR", 37.9838, 23.7275), ("Oslo", "NO", 59.9139, 10.7522),
    ("New York", "US", 40.7128, -74.006), ("Los Angeles", "US", 34.0522, -118.2437),
    ("Toronto", "CA", 43.6532, -79.3832), ("Mexico City", "MX", 19.4326, -99.1332),
    ("Lima", "PE", -12.0464, -77.0428), ("Rio de Janeiro", "BR", -22.9068, -43.1729),
    ("Buenos Aires", "AR", -34.6037, -58.3816), ("Bogota", "CO", 4.711, -74.0721),
    ("Tokyo", "JP", 35.6762, 139.6503), ("Seoul", "KR", 37.5665, 126.978),
    ("Bangkok", "TH", 13.7563, 100.5018), ("Singapore", "SG", 1.3521, 103.8198),
    ("Mumbai", "IN", 19.076, 72.8777), ("Dubai", "AE", 25.2048, 55.2708),
    ("Istanbul", "TR", 41.0082, 28.9784), ("Beijing", "CN", 39.9042, 116.4074),
    ("Cairo", "EG", 30.0444, 31.2357), ("Cape Town", "ZA", -33.9249, 18.4241),
    ("Nairobi", "KE", -1.2921, 36.8219), ("Marrakech", "MA", 31.6295, -7.9811),
    ("Sydney", "AU", -33.8688, 151.2093), ("Auckland", "NZ", -36.8485, 174.7633),
    ("Reykjavik", "IS", 64.1466, -21.9426), ("Stockholm", "SE", 59.3293, 18.0686),
    ("Prague", "CZ", 50.0755, 14.4378), ("Budapest", "HU", 47.4979, 19.0402),
]


def _unique_names(n: int) -> list[tuple[str, str]]:
    combos = [(f, l) for f in FIRST for l in LAST]
    random.shuffle(combos)
    return combos[:n]


def seed() -> int:
    random.seed(42)
    db = SessionLocal()
    created = 0
    try:
        names = _unique_names(COUNT)
        for i, (first, last) in enumerate(names):
            username = f"{first.lower()}{last.lower()}{i:02d}"
            if db.scalar(select(User.id).where(User.username == username)):
                continue

            home = random.choice(CITIES)
            user = User(
                email=f"{username}@test.trekrank.app", username=username,
                display_name=f"{first} {last}", password_hash=hash_password(PASSWORD),
                home_city=home[0], home_country=home[1],
                bio="Test traveller.",
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            created += 1

            # Varied number of trips → spread of stats for competitive ranks.
            n_trips = random.randint(1, 16)
            dests = random.sample(CITIES, min(n_trips, len(CITIES)))
            for j, (city, cc, lat, lng) in enumerate(dests):
                trip = Trip(
                    user_id=user.id, dest_city=city, dest_country=cc, dest_lat=lat, dest_lng=lng,
                    origin_city=home[0], origin_country=home[1], origin_lat=home[2], origin_lng=home[3],
                    transport_mode=random.choice(["flight", "train", "car", "bus"]),
                    start_date=f"2026-{(j % 12) + 1:02d}-{(j % 27) + 1:02d}",
                    is_public=True, status="processing",
                )
                db.add(trip)
                db.commit()
                db.refresh(trip)
                process_trip_sync(str(trip.id))

            recalculate_user_stats(db, user)
            db.commit()

        for metric in ("countries", "cities", "km", "trips"):
            try:
                leaderboard.rebuild_global(db, metric)
            except Exception:
                pass
        return created
    finally:
        db.close()


if __name__ == "__main__":
    n = seed()
    print(f"Bulk seed: created {n} new test users (password '{PASSWORD}').")
