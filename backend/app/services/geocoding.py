"""Free geocoding via Nominatim (OpenStreetMap), with Redis caching + polite rate limiting.

Nominatim's usage policy asks for <= 1 request/second and a descriptive User-Agent.
Results are cached in Redis for 30 days so repeated cities don't hit the API.
"""
import json
import math
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


def geocode_place(name: str) -> tuple[float, float] | None:
    """Geocode restricted to settlements (cities/towns/villages) — safe for
    guessing place names out of free text, since ordinary words won't match."""
    if not name or len(name) < 3:
        return None
    key = f"geoplace:{name.strip().lower()}"
    cached = redis_client.get(key)
    if cached is not None:
        data = json.loads(cached)
        return (data["lat"], data["lng"]) if data else None

    params = {"q": name, "format": "json", "limit": 1,
              "addressdetails": 0, "featuretype": "settlement"}
    try:
        _throttle()
        resp = httpx.get(settings.nominatim_url, params=params,
                         headers={"User-Agent": settings.geocode_user_agent}, timeout=15.0)
        resp.raise_for_status()
        results = resp.json()
    except (httpx.HTTPError, ValueError):
        return None
    if not results:
        redis_client.setex(key, settings.geocode_cache_ttl, json.dumps(None))
        return None
    lat, lng = float(results[0]["lat"]), float(results[0]["lon"])
    redis_client.setex(key, settings.geocode_cache_ttl, json.dumps({"lat": lat, "lng": lng}))
    return lat, lng


def find_place(name: str, lat: float, lng: float, radius_km: float = 10.0) -> dict | None:
    """Look up a specific named venue near a point (OSM/Nominatim, keyless).
    Returns a normalised candidate dict like yelp/foursquare search results, or
    None when no such place exists nearby — used to verify user-requested venues
    when no paid source is configured."""
    if not name or len(name.strip()) < 3:
        return None
    key = f"geovenue:{name.strip().lower()}:{round(lat,2)}:{round(lng,2)}"
    cached = redis_client.get(key)
    if cached is not None:
        return json.loads(cached)

    # viewbox bounds the search to ~radius_km around the point; bounded=1 makes
    # it a hard filter, so a same-named place in another city can't match.
    dlat = radius_km / 111.0
    dlng = radius_km / (111.0 * max(0.1, math.cos(math.radians(lat))))
    params = {"q": name, "format": "json", "limit": 3, "addressdetails": 0,
              "bounded": 1,
              "viewbox": f"{lng - dlng},{lat + dlat},{lng + dlng},{lat - dlat}"}
    try:
        _throttle()
        resp = httpx.get(settings.nominatim_url, params=params,
                         headers={"User-Agent": settings.geocode_user_agent}, timeout=15.0)
        resp.raise_for_status()
        results = resp.json()
    except (httpx.HTTPError, ValueError):
        return None
    out = None
    for r in results or []:
        found = (r.get("display_name") or "").split(",")[0]
        out = {
            "source": "osm", "name": found or name.strip(),
            "lat": float(r["lat"]), "lng": float(r["lon"]),
            "rating": None, "review_count": None, "price": None,
            "categories": [t for t in [r.get("type", "").replace("_", " ")] if t],
            "address": r.get("display_name"), "image": None, "url": None,
        }
        break
    redis_client.setex(key, settings.geocode_cache_ttl, json.dumps(out))
    return out


def _reverse_url() -> str:
    """Nominatim reverse endpoint, derived from the configured /search URL."""
    return settings.nominatim_url.rsplit("/search", 1)[0] + "/reverse"


def reverse_geocode(lat: float, lng: float) -> dict | None:
    """Return {country_code, place} for a coordinate, or None if not found.

    country_code is an upper-case ISO-2 (e.g. "JP"); place is the best available
    locality name (city/town/village). Cached by coords rounded to ~1km so nearby
    photos reuse one lookup. Negative results are cached too.
    """
    if lat is None or lng is None:
        return None
    key = f"revgeo:{round(lat, 2)}:{round(lng, 2)}"
    cached = redis_client.get(key)
    if cached is not None:
        data = json.loads(cached)
        return data or None

    params = {
        "lat": lat, "lon": lng, "format": "json",
        "zoom": 10, "addressdetails": 1,
    }
    headers = {"User-Agent": settings.geocode_user_agent}
    try:
        _throttle()
        resp = httpx.get(_reverse_url(), params=params, headers=headers, timeout=15.0)
        resp.raise_for_status()
        data = resp.json()
    except (httpx.HTTPError, ValueError):
        return None

    addr = (data or {}).get("address") or {}
    cc = addr.get("country_code")
    if not cc:
        redis_client.setex(key, settings.geocode_cache_ttl, json.dumps(None))
        return None
    place = (addr.get("city") or addr.get("town") or addr.get("village")
             or addr.get("county") or addr.get("state"))
    result = {"country_code": cc.upper(), "place": place}
    redis_client.setex(key, settings.geocode_cache_ttl, json.dumps(result))
    return result
