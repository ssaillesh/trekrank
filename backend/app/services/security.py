"""Password hashing and JWT creation/verification."""
from datetime import datetime, timedelta, timezone

from jose import jwt, JWTError
from passlib.context import CryptContext

from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    # bcrypt has a 72-byte limit; truncate defensively.
    return pwd_context.hash(password[:72])


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password[:72], password_hash)


def _create_token(subject: str, minutes: int, token_type: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "type": token_type,
        "iat": now,
        "exp": now + timedelta(minutes=minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: str) -> str:
    return _create_token(user_id, settings.access_token_expire_minutes, "access")


def create_refresh_token(user_id: str) -> str:
    return _create_token(user_id, settings.refresh_token_expire_minutes, "refresh")


def create_reset_token(user_id: str) -> str:
    """Short-lived token used to authorize a password reset."""
    return _create_token(user_id, 15, "reset")


def decode_token(token: str, expected_type: str | None = None) -> dict | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None
    if expected_type and payload.get("type") != expected_type:
        return None
    return payload
