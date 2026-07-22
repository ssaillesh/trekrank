"""Prometheus metrics: itinerary generation and PostGIS query timings.

Generic HTTP request latency/throughput (giving p95 per-route "free") is
handled by prometheus-fastapi-instrumentator in main.py — this module only
holds the app-specific metrics that library can't infer on its own.
"""
import time
from contextlib import contextmanager

from prometheus_client import Counter, Histogram

# Buckets tuned around the "sub-200ms itinerary generation" target, with
# headroom for slow paths (LLM narration, cold external API calls).
itinerary_generation_seconds = Histogram(
    "trekrank_itinerary_generation_seconds",
    "Time to build an itinerary (planner.build_plan/build_trip)",
    ["kind"],  # "single_day" | "multi_day"
    buckets=(0.05, 0.1, 0.2, 0.3, 0.5, 0.75, 1, 2, 3, 5, 8, 13, float("inf")),
)

itineraries_generated_total = Counter(
    "trekrank_itineraries_generated_total",
    "Number of itineraries successfully generated",
    ["kind"],
)

postgis_query_seconds = Histogram(
    "trekrank_postgis_query_seconds",
    "Time spent in PostGIS geospatial queries",
    ["query_type"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, float("inf")),
)


@contextmanager
def time_itinerary_generation(kind: str):
    start = time.perf_counter()
    try:
        yield
    finally:
        itinerary_generation_seconds.labels(kind=kind).observe(time.perf_counter() - start)
    itineraries_generated_total.labels(kind=kind).inc()


@contextmanager
def time_postgis_query(query_type: str):
    start = time.perf_counter()
    try:
        yield
    finally:
        postgis_query_seconds.labels(query_type=query_type).observe(time.perf_counter() - start)
