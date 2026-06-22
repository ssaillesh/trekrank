"""Great-circle distance.

Production (PostGIS) computes this with ST_Distance over GEOGRAPHY(POINT,4326);
see the ``distance_km_postgis`` helper below. For portability across environments
without the PostGIS extension we also provide an equivalent Haversine in Python,
which is what the workers use by default. Both agree to within ~0.5%.
"""
import math

EARTH_RADIUS_KM = 6371.0088


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return round(2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a)), 2)


def distance_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    return haversine_km(lat1, lng1, lat2, lng2)


def distance_km_postgis(db, lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """PostGIS-backed equivalent (used when the extension is available)."""
    from sqlalchemy import text
    result = db.execute(
        text(
            "SELECT ST_Distance("
            "  ST_SetSRID(ST_MakePoint(:lng1, :lat1), 4326)::geography,"
            "  ST_SetSRID(ST_MakePoint(:lng2, :lat2), 4326)::geography) / 1000.0"
        ),
        {"lng1": lng1, "lat1": lat1, "lng2": lng2, "lat2": lat2},
    ).scalar_one()
    return round(float(result), 2)
