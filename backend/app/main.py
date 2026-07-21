"""TrekRank FastAPI application entrypoint."""
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.middleware.rate_limit import RateLimitMiddleware
from app.api import (
    auth, users, trips, friends, leaderboards, feed, badges, challenges, share, waitlist,
    hotspots, plan,
)

app = FastAPI(
    title="TrekRank API",
    version="0.1.0",
    description="Travel logging, leaderboards, badges and share cards.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RateLimitMiddleware)

# Serve locally-stored media (share cards) when STORAGE_BACKEND=local.
if settings.storage_backend == "local":
    os.makedirs(settings.local_storage_dir, exist_ok=True)
    app.mount("/media", StaticFiles(directory=settings.local_storage_dir), name="media")

P = settings.api_v1_prefix
for r in (auth, users, trips, friends, leaderboards, feed, badges, challenges, share, waitlist,
          hotspots, plan):
    app.include_router(r.router, prefix=P)


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok", "app": settings.app_name, "env": settings.environment}


@app.get("/metrics", tags=["meta"])
def metrics():
    """Minimal Prometheus-style metrics stub (extend with prometheus_client in prod)."""
    return {"trekrank_up": 1}


@app.get("/", tags=["meta"])
def root():
    return {"name": "TrekRank API", "docs": "/docs", "version": "0.1.0"}
