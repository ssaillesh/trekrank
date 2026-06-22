"""Live end-to-end smoke test against a running TrekRank API (default :8001).

Exercises register -> create trip -> async worker geocode/distance -> stats ->
badges -> friends -> leaderboard -> feed -> share card. Hits real Nominatim.
"""
import sys
import time
import random

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8001/api/v1"


def reg(c, prefix):
    u = f"{prefix}_{random.randint(1000, 999999)}"
    r = c.post(f"{BASE}/auth/register", json={
        "email": f"{u}@ex.com", "username": u, "display_name": prefix.title(),
        "password": "password123",
    })
    r.raise_for_status()
    d = r.json()
    return u, d["access_token"]


def h(t):
    return {"Authorization": f"Bearer {t}"}


def main():
    c = httpx.Client(timeout=30)
    user, token = reg(c, "smoke")
    print(f"[1] registered @{user}")

    r = c.post(f"{BASE}/trips", headers=h(token), json={
        "title": "Spring break in Tokyo", "origin_city": "Toronto", "origin_country": "CA",
        "dest_city": "Tokyo", "dest_country": "JP", "transport_mode": "flight",
        "start_date": "2026-03-15", "end_date": "2026-03-25",
    })
    r.raise_for_status()
    trip = r.json()
    print(f"[2] created trip {trip['id']} status={trip['status']} distance_km={trip['distance_km']}")

    # wait for the Celery worker to geocode + compute distance
    for _ in range(15):
        time.sleep(1)
        d = c.get(f"{BASE}/trips/{trip['id']}", headers=h(token)).json()
        if d["status"] == "done":
            break
    print(f"[3] worker done: status={d['status']} distance_km={d['distance_km']} "
          f"(live Nominatim Toronto->Tokyo)")
    assert d["distance_km"] and d["distance_km"] > 9000, "distance not computed"

    stats = c.get(f"{BASE}/users/me", headers=h(token)).json()
    print(f"[4] stats: countries={stats['total_countries']} cities={stats['total_cities']} "
          f"km={stats['total_km']} trips={stats['total_trips']} streak={stats['current_streak']}")

    # Badge evaluation runs just after the trip is marked done; poll briefly.
    badges = []
    for _ in range(10):
        badges = [b["id"] for b in c.get(f"{BASE}/badges/me", headers=h(token)).json() if b["earned"]]
        if "first_trip" in badges:
            break
        time.sleep(1)
    print(f"[5] badges earned: {badges}")
    assert "first_trip" in badges and "first_flight" in badges

    mp = c.get(f"{BASE}/users/{user}/map", headers=h(token)).json()
    print(f"[6] map: {len(mp['countries'])} countries, cities={[ (ci['name'], round(ci['lat'],2), round(ci['lng'],2)) for ci in mp['cities'] ]}")

    # friends + leaderboard
    u2, t2 = reg(c, "buddy")
    c.post(f"{BASE}/friends/request", headers=h(token), json={"username": u2})
    fid = c.get(f"{BASE}/friends/requests", headers=h(t2)).json()[0]["friendship_id"]
    c.post(f"{BASE}/friends/accept/{fid}", headers=h(t2))
    print(f"[7] friends: @{user} <-> @{u2} accepted")

    lb = c.get(f"{BASE}/leaderboards/friends", headers=h(token),
               params={"metric": "countries", "period": "all_time"}).json()
    print(f"[8] friend leaderboard (countries): " +
          ", ".join(f"#{r['rank']} @{r['user']['username']}={r['value']}" for r in lb["rankings"]) +
          f"  my_rank={lb['my_rank']}")

    feed = c.get(f"{BASE}/feed/me", headers=h(token)).json()
    print(f"[9] my feed events: {[i['event_type'] for i in feed['items']]}")

    card = c.post(f"{BASE}/share/card", headers=h(token),
                  json={"card_type": "year_recap", "year": 2026}).json()
    print(f"[10] share card: {card['image_url']}")

    print("\nALL SMOKE CHECKS PASSED ✅")


if __name__ == "__main__":
    main()
