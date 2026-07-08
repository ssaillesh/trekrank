# TrekRank

Travel-logging social app: log trips, auto-compute distances, climb friend &
global leaderboards, earn badges, and generate shareable year-in-travel cards.

This repo contains a **working FastAPI backend** (verified end-to-end) and a
**full SwiftUI iOS client**.

```
iOS (SwiftUI)  ──HTTP──▶  FastAPI  ──▶  PostgreSQL (PostGIS-ready)
                                   ├──▶  Redis (leaderboards, cache, rate limit)
                                   ├──▶  Celery workers (geocode, distance, badges, share cards)
                                   └──▶  Object storage (local disk in dev / S3·MinIO in prod)
                                   
Geocoding: Nominatim / OpenStreetMap (free, no API key)
```

Everything uses **free / open-source components** — no paid APIs. Geocoding is the
free Nominatim endpoint; photo/share-card storage defaults to the local filesystem.

---

## What's implemented

**Backend (Python 3.10+, FastAPI):** all endpoints from the spec —
auth (email register/login + JWT refresh + Apple sign-in stub + GDPR delete),
users/profile/stats/map/search, trips CRUD + photo upload + onboarding backfill,
friends (request/accept/reject/suggestions), friend & global leaderboards (Redis
sorted sets), cursor-paginated activity feed, badges (20 seeded) + evaluation,
group challenges, and Instagram-Story share-card generation.

**4 Celery workers:** trip processor (geocode → distance → visited tables → stats →
leaderboards → feed → badge trigger), badge evaluator, photo processor
(EXIF strip + thumbnail/medium), share-card generator (Pillow, 1080×1920 PNG).

**iOS app (SwiftUI, iOS 17):** auth, feed, trips list + add-trip, friend/global
leaderboards, MapKit world map of visited cities, profile with stats/badges and
one-tap share-card generation.

**Tests:** 10 pytest integration tests (trips, badges, leaderboards, feed) — all green.

---

## PostGIS

This runs on **PostGIS** as the spec intends: coordinates are stored as
`GEOGRAPHY(POINT, 4326)` columns with **GiST spatial indexes**, and trip distances
are computed with **`ST_Distance`** over the geography type
(`app/services/distance.py` → `distance_km_postgis`). `docker-compose.yml` uses the
`postgis/postgis:16-3.4` image; the native setup uses Homebrew `postgis` on
PostgreSQL 18. The migration enables the extension automatically.

> Portability note: `app/services/distance.py` also ships an equivalent Haversine
> (`distance_km`) that matches `ST_Distance` to ~0.5%, so the distance logic can run
> on vanilla PostgreSQL if PostGIS is ever unavailable.

---

## Run it — Option A: native (no Docker)

What this machine has: Homebrew PostgreSQL 18 + Redis (running), Python 3.10.

```bash
# prerequisites
brew services start postgresql@18
brew services start redis
createdb trekrank

cd backend
./run_local.sh setup           # venv + deps + migrate + seed badges
./run_local.sh worker          # terminal 1: Celery worker
./run_local.sh api             # terminal 2: API on http://127.0.0.1:8001
./run_local.sh smoke           # terminal 3: live end-to-end test
```

Interactive API docs: <http://127.0.0.1:8001/docs>

```bash
./run_local.sh test            # run the pytest suite
```

## Run it — Option B: full stack via Docker

Brings up Postgres+PostGIS, Redis, MinIO, Prometheus, Grafana, API, and worker:

```bash
docker compose up --build
# API on :8000, MinIO console :9001, Grafana :3000, Prometheus :9090
```

(Docker isn't installed on the current machine, so Option A is the verified path.)

---

## iOS app

```
ios/TrekRank/
```

Requires **Xcode** (only Command Line Tools are present here, so it couldn't be
compiled in this environment — the Swift sources parse cleanly).

```bash
brew install xcodegen
cd ios/TrekRank
xcodegen generate        # produces TrekRank.xcodeproj
open TrekRank.xcodeproj   # run on the iOS Simulator (⌘R)
```

Or create a new SwiftUI iOS App in Xcode and drag in `ios/TrekRank/TrekRank/`.
Point the client at your API in `Config.swift` (defaults to `http://127.0.0.1:8001`;
the Simulator can reach `localhost`, a physical device needs your Mac's LAN IP).

---

## Project layout

```
trekrank/
├── backend/
│   ├── app/
│   │   ├── main.py              FastAPI app + middleware + static media
│   │   ├── config.py            env-driven settings
│   │   ├── database.py          SQLAlchemy engine/session
│   │   ├── models/              ORM models (users, trips, badges, …)
│   │   ├── schemas/             Pydantic request/response models
│   │   ├── api/                 routers (auth, users, trips, friends, …)
│   │   ├── services/            geocoding, distance, stats, badges, leaderboard, share
│   │   ├── workers/             Celery app + 4 workers
│   │   ├── middleware/          JWT auth + Redis rate limiting
│   │   └── data/countries.py    ISO country + continent reference data
│   ├── alembic/                 migrations (0001_init)
│   ├── scripts/                 seed_badges, smoke_test
│   ├── tests/                   pytest suite
│   └── run_local.sh             native launcher
├── ios/TrekRank/                SwiftUI client (+ XcodeGen project.yml)
├── docker-compose.yml           full prod-like stack (PostGIS/MinIO/Prom/Grafana)
└── infra/prometheus.yml
```

## API quick reference

`/api/v1` prefix. Highlights:

| Method | Path | Notes |
|---|---|---|
| POST | `/auth/register` `/auth/login` `/auth/refresh` | JWT |
| POST | `/trips` | returns `201` immediately; worker fills `distance_km` async |
| POST | `/trips/backfill` | bulk onboarding import |
| GET | `/users/{username}/stats` `/users/{username}/map` | detailed stats / map data |
| POST | `/friends/request`, `/friends/accept/{id}` | friend graph |
| GET | `/leaderboards/friends?metric=countries&period=2026` | Redis ZSET |
| GET | `/feed` | cursor-paginated, friends only |
| GET | `/badges/me` | earned + locked |
| POST | `/share/card` | 1080×1920 PNG |

Full interactive docs at `/docs`.
