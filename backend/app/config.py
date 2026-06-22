"""Application configuration loaded from environment variables."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Core
    app_name: str = "TrekRank"
    api_v1_prefix: str = "/api/v1"
    environment: str = "development"

    # Database
    database_url: str = "postgresql+psycopg2://saillesh@localhost:5432/trekrank"

    # Redis (broker + cache + leaderboards + rate limiting)
    redis_url: str = "redis://localhost:6379/0"

    # JWT
    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # 1 day
    refresh_token_expire_minutes: int = 60 * 24 * 30  # 30 days

    # Storage: "local" (filesystem) or "s3" (MinIO/S3). MVP defaults to local.
    storage_backend: str = "local"
    local_storage_dir: str = "./media"
    public_base_url: str = "http://localhost:8000"

    # S3 / MinIO (used only when storage_backend == "s3")
    s3_endpoint: str = "http://localhost:9000"
    s3_bucket: str = "trekrank-photos"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"

    # Geocoding (Nominatim / OpenStreetMap — free, no key)
    nominatim_url: str = "https://nominatim.openstreetmap.org/search"
    geocode_user_agent: str = "TrekRank/0.1 (mvp; contact dev@trekrank.app)"
    geocode_cache_ttl: int = 60 * 60 * 24 * 30  # 30 days

    # Rate limiting (requests per window per client)
    rate_limit_requests: int = 120
    rate_limit_window_seconds: int = 60

    # Leaderboard cache TTL
    leaderboard_ttl_seconds: int = 300  # 5 minutes


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
