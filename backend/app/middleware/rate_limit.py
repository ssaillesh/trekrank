"""Redis-backed fixed-window rate limiting middleware."""
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.config import settings
from app.redis_client import redis_client


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Identify client by Authorization token if present, else IP.
        auth = request.headers.get("authorization", "")
        client_key = auth[-32:] if auth else (request.client.host if request.client else "anon")
        window = int(time.time()) // settings.rate_limit_window_seconds
        key = f"ratelimit:{client_key}:{window}"

        try:
            count = redis_client.incr(key)
            if count == 1:
                redis_client.expire(key, settings.rate_limit_window_seconds)
        except Exception:
            # Fail open if Redis is unavailable.
            return await call_next(request)

        if count > settings.rate_limit_requests:
            return JSONResponse(
                {"detail": "Rate limit exceeded. Try again shortly."},
                status_code=429,
            )
        return await call_next(request)
