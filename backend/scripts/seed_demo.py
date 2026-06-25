"""Seed a few demo users with trips, badges, spot recommendations, friendships,
and a populated global leaderboard. Idempotent: skips users that already exist.

Run:  python -m scripts.seed_demo
Log in as any demo user with password  TrekDemo123!  to see a lively feed +
competitive Ranks board (they're all friends with each other).
"""
import itertools

from sqlalchemy import select

from app.database import SessionLocal
from app.models import User, Trip, ActivityFeed, Friendship
from app.services.security import hash_password
from app.services.stats import recalculate_user_stats
from app.services import leaderboard
from app.workers.trip_processor import process_trip_sync

PASSWORD = "TrekDemo123!"

# username, display, email, (home_city, home_country, home_lat, home_lng),
# trips [(city, country, lat, lng, transport, date)], recs [(text, city, country)]
DEMO = [
    ("alex_wanders", "Alex Rivera", "alex@demo.trekrank.app",
     ("Lisbon", "PT", 38.7223, -9.1393),
     [("Paris", "FR", 48.8566, 2.3522, "flight", "2026-01-10"),
      ("Rome", "IT", 41.9028, 12.4964, "flight", "2026-02-14"),
      ("Berlin", "DE", 52.52, 13.405, "train", "2026-03-02"),
      ("Madrid", "ES", 40.4168, -3.7038, "train", "2026-03-20"),
      ("Amsterdam", "NL", 52.3676, 4.9041, "flight", "2026-04-11"),
      ("Vienna", "AT", 48.2082, 16.3738, "train", "2026-05-05")],
     [("The rooftop near Sacré-Cœur has the best free sunset over Paris — go early.", "Paris", "FR"),
      ("In Rome, skip the chain gelato; Fatamorgana near the Pantheon is the real deal.", "Rome", "IT")]),

    ("mia_globe", "Mia Chen", "mia@demo.trekrank.app",
     ("San Francisco", "US", 37.7749, -122.4194),
     [("Tokyo", "JP", 35.6762, 139.6503, "flight", "2026-01-22"),
      ("Sydney", "AU", -33.8688, 151.2093, "flight", "2026-02-28"),
      ("Dubai", "AE", 25.2048, 55.2708, "flight", "2026-04-03"),
      ("Singapore", "SG", 1.3521, 103.8198, "flight", "2026-05-18")],
     [("Skip touristy Tokyo — Yanaka's old streets and tiny izakayas are pure magic.", "Tokyo", "JP"),
      ("Sydney: catch the ferry to Manly at sunset, cheaper than any harbour cruise.", "Sydney", "AU")]),

    ("liam_roams", "Liam O'Brien", "liam@demo.trekrank.app",
     ("Dublin", "IE", 53.3498, -6.2603),
     [("London", "GB", 51.5074, -0.1278, "flight", "2026-01-15"),
      ("Edinburgh", "GB", 55.9533, -3.1883, "train", "2026-02-09"),
      ("Manchester", "GB", 53.4808, -2.2426, "train", "2026-03-12"),
      ("Lyon", "FR", 45.764, 4.8357, "flight", "2026-04-22"),
      ("Porto", "PT", 41.1579, -8.6291, "flight", "2026-05-30")],
     [("Edinburgh's Arthur's Seat at dawn is the best free view in the UK.", "Edinburgh", "GB"),
      ("Porto: the Livraria Lello bookshop is gorgeous but go at opening to beat the queues.", "Porto", "PT")]),

    ("sara_trails", "Sara Khan", "sara@demo.trekrank.app",
     ("Chicago", "US", 41.8781, -87.6298),
     [("New York", "US", 40.7128, -74.006, "flight", "2026-02-01"),
      ("Toronto", "CA", 43.6532, -79.3832, "flight", "2026-03-08"),
      ("Mexico City", "MX", 19.4326, -99.1332, "flight", "2026-04-19"),
      ("Lima", "PE", -12.0464, -77.0428, "flight", "2026-05-25")],
     [("Mexico City's Mercado Roma is a foodie heaven — go hungry.", "Mexico City", "MX"),
      ("In Lima, the ceviche at a market in Surquillo beats any fancy restaurant.", "Lima", "PE")]),
]


def seed() -> dict:
    db = SessionLocal()
    created_users = 0
    user_ids = []
    try:
        for username, display, email, home, trips, recs in DEMO:
            existing = db.scalar(select(User).where(User.username == username))
            if existing:
                user_ids.append(existing.id)
                continue

            hc, hcc, hlat, hlng = home
            user = User(email=email, username=username, display_name=display,
                        password_hash=hash_password(PASSWORD),
                        home_city=hc, home_country=hcc,
                        bio=f"Demo traveller exploring the world.")
            db.add(user)
            db.commit()
            db.refresh(user)
            user_ids.append(user.id)
            created_users += 1

            # Trips (origin = home so distance is computed), processed synchronously.
            for city, cc, lat, lng, mode, d in trips:
                trip = Trip(user_id=user.id, dest_city=city, dest_country=cc,
                            dest_lat=lat, dest_lng=lng, origin_city=hc, origin_country=hcc,
                            origin_lat=hlat, origin_lng=hlng, transport_mode=mode,
                            start_date=d, is_public=True, status="processing")
                db.add(trip)
                db.commit()
                db.refresh(trip)
                process_trip_sync(str(trip.id))

            # Spot recommendations
            for text, city, cc in recs:
                db.add(ActivityFeed(user_id=user.id, event_type="recommendation",
                                    activity_metadata={"text": text, "city": city, "country": cc}))
            db.commit()
            recalculate_user_stats(db, user)
            db.commit()

        # Make all demo users friends with each other (so feeds + Ranks are lively).
        for a, b in itertools.combinations(user_ids, 2):
            exists = db.scalar(select(Friendship.id).where(
                ((Friendship.requester_id == a) & (Friendship.addressee_id == b)) |
                ((Friendship.requester_id == b) & (Friendship.addressee_id == a))
            ))
            if not exists:
                db.add(Friendship(requester_id=a, addressee_id=b, status="accepted"))
        db.commit()

        # Refresh leaderboards.
        for u in db.execute(select(User).where(User.id.in_(user_ids))).scalars():
            try:
                leaderboard.rebuild_for_user(db, u)
            except Exception:
                pass
        for metric in ("countries", "cities", "km", "trips"):
            try:
                leaderboard.rebuild_global(db, metric)
            except Exception:
                pass

        return {"created_users": created_users, "total_demo": len(DEMO)}
    finally:
        db.close()


if __name__ == "__main__":
    result = seed()
    print(f"Demo seed: {result['created_users']} new user(s) of {result['total_demo']}.")
    print(f"Log in with password '{PASSWORD}' as e.g. alex_wanders / mia_globe / liam_roams / sara_trails.")
