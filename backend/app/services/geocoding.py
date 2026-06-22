"""Free geocoding via Nominatim (OpenStreetMap), with Redis caching + polite rate limiting.

Nominatim's usage policy asks for <= 1 request/second and a descriptive User-Agent.
Results are cached in Redis for 30 days so repeated cities don't hit the API.
"""
import json
import time

import httpx

from app.config import settings
from app.redis_client import redis_client

_LAST_CALL_KEY = "geocode:last_call_ts"


def _cache_key(city: str, country: str) -> str:
    return f"geocode:{(country or '').upper()}:{city.strip().lower()}"


def _throttle() -> None:
    """Ensure at least ~1.1s between live Nominatim calls (process-safe via Redis)."""
    last = redis_client.get(_LAST_CALL_KEY)
    if last:
        elapsed = time.time() - float(last)
        if elapsed < 1.1:
            time.sleep(1.1 - elapsed)
    redis_client.set(_LAST_CALL_KEY, str(time.time()))


def geocode(city: str, country: str | None) -> tuple[float, float] | None:
    """Return (lat, lng) for a city/country, or None if not found.

    Cached results (including negative lookups) avoid repeat API calls.
    """
    if not city:
        return None
    key = _cache_key(city, country or "")
    cached = redis_client.get(key)
    if cached is not None:
        data = json.loads(cached)
        return (data["lat"], data["lng"]) if data else None

    params = {
        "q": f"{city}, {country}" if country else city,
        "format": "json",
        "limit": 1,
        "addressdetails": 0,
    }
    if country:
        params["countrycodes"] = country.lower()

    headers = {"User-Agent": settings.geocode_user_agent}
    try:
        _throttle()
        resp = httpx.get(settings.nominatim_url, params=params, headers=headers, timeout=15.0)
        resp.raise_for_status()
        results = resp.json()
    except (httpx.HTTPError, ValueError):
        return None

    if not results:
        redis_client.setex(key, settings.geocode_cache_ttl, json.dumps(None))
        return None

    lat = float(results[0]["lat"])
    lng = float(results[0]["lon"])
    redis_client.setex(key, settings.geocode_cache_ttl, json.dumps({"lat": lat, "lng": lng}))
    return lat, lng
