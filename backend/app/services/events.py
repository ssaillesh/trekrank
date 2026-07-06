"""Live events via the Ticketmaster Discovery API — free (concerts, sports,
comedy, festivals). Use your app's *Consumer Key* as TICKETMASTER_API_KEY.

Returns [] when no key is set, so the planner degrades gracefully.
"""
import json

import httpx

from app.config import settings
from app.redis_client import redis_client

_URL = "https://app.ticketmaster.com/discovery/v2/events.json"
_TTL = 60 * 60 * 3  # 3h


def available() -> bool:
    return bool(settings.ticketmaster_api_key)


def classification_for(vibe: str | None, interests: str | None) -> str | None:
    it = (interests or "").lower()
    if any(w in it for w in ["concert", "music", "dj", "show", "band", "festival"]):
        return "Music"
    if any(w in it for w in ["game", "sports", "raptors", "jays", "leafs", "hockey", "basketball", "baseball"]):
        return "Sports"
    if any(w in it for w in ["comedy", "standup", "stand-up"]):
        return "Comedy"
    if vibe == "night_out":
        return "Music"
    return None  # all types


def search_events(lat: float, lng: float, *, radius_km: int = 20, size: int = 12,
                  classification: str | None = None) -> list[dict]:
    if not available():
        return []
    key = f"tm:{round(lat, 2)}:{round(lng, 2)}:{radius_km}:{classification}"
    cached = redis_client.get(key)
    if cached is not None:
        return json.loads(cached)

    params = {
        "apikey": settings.ticketmaster_api_key,
        "latlong": f"{lat},{lng}", "radius": radius_km, "unit": "km",
        "size": size, "sort": "date,asc",
    }
    if classification:
        params["classificationName"] = classification
    try:
        r = httpx.get(_URL, params=params, timeout=15.0)
        r.raise_for_status()
        data = r.json()
    except (httpx.HTTPError, ValueError):
        return []

    out = []
    for e in data.get("_embedded", {}).get("events", []):
        venue = (e.get("_embedded", {}).get("venues") or [{}])[0]
        loc = venue.get("location") or {}
        start = e.get("dates", {}).get("start", {})
        seg = ((e.get("classifications") or [{}])[0].get("segment") or {}).get("name")
        prices = e.get("priceRanges") or []
        img = next((im["url"] for im in e.get("images", []) if im.get("width", 0) >= 600), None)
        out.append({
            "name": e.get("name"),
            "venue": venue.get("name"),
            "lat": float(loc["latitude"]) if loc.get("latitude") else None,
            "lng": float(loc["longitude"]) if loc.get("longitude") else None,
            "date": start.get("localDate"),
            "time": start.get("localTime"),
            "category": seg,
            "url": e.get("url"),
            "price_min": prices[0]["min"] if prices else None,
            "price_max": prices[0]["max"] if prices else None,
            "image": img,
        })
    redis_client.setex(key, _TTL, json.dumps(out))
    return out
