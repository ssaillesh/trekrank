"""Pytest fixtures: FastAPI TestClient against the real Postgres+PostGIS DB.

Geocoding is monkeypatched to a small offline lookup so tests don't hit Nominatim
and Celery runs eagerly (in-process). Each test runs inside its own data namespace
via unique usernames/emails.
"""
import os
import uuid

os.environ.setdefault("CELERY_TASK_ALWAYS_EAGER", "1")
# Don't let the shared TestClient IP trip the rate limiter across the whole suite.
os.environ.setdefault("RATE_LIMIT_REQUESTS", "1000000")

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import geocoding
from app.redis_client import redis_client
from scripts.seed_badges import seed

# Minimal offline gazetteer for deterministic tests.
_FIXTURE_COORDS = {
    ("toronto", "CA"): (43.6532, -79.3832),
    ("tokyo", "JP"): (35.6762, 139.6503),
    ("london", "GB"): (51.5074, -0.1278),
    ("paris", "FR"): (48.8566, 2.3522),
    ("montreal", "CA"): (45.5019, -73.5674),
    ("new york", "US"): (40.7128, -74.0060),
}


@pytest.fixture(scope="session", autouse=True)
def _seed_badges():
    seed()
    yield


@pytest.fixture(autouse=True)
def _offline_geocode(monkeypatch):
    def fake_geocode(city, country):
        if not city:
            return None
        return _FIXTURE_COORDS.get((city.strip().lower(), (country or "").upper()))
    monkeypatch.setattr(geocoding, "geocode", fake_geocode)
    # also patch the imported reference in the worker module
    import app.workers.trip_processor as tp
    monkeypatch.setattr(tp, "geocode", fake_geocode)
    yield


@pytest.fixture(autouse=True)
def _clear_leaderboard_cache():
    """Isolate Redis leaderboard cache between tests for deterministic rankings."""
    for key in redis_client.scan_iter("leaderboard:*"):
        redis_client.delete(key)
    yield


@pytest.fixture
def client():
    return TestClient(app)


def make_user(client, prefix="user"):
    uid = uuid.uuid4().hex[:8]
    body = {
        "email": f"{prefix}_{uid}@example.com",
        "username": f"{prefix}_{uid}",
        "display_name": prefix.title(),
        "password": "password123",
    }
    resp = client.post("/api/v1/auth/register", json=body)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    return data["user"], data["access_token"]


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}
