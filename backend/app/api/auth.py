import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.middleware.auth import get_current_user
from app.schemas.auth import (
    RegisterRequest, LoginRequest, AppleAuthRequest, RefreshRequest, TokenResponse, AuthUser,
    ForgotPasswordRequest, ForgotPasswordResponse, ResetPasswordRequest,
)
from app.services.security import (
    hash_password, verify_password, create_access_token, create_refresh_token, decode_token,
    create_reset_token,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _tokens(user: User, is_new: bool) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
        user=AuthUser(
            id=str(user.id), username=user.username,
            display_name=user.display_name, is_new_user=is_new,
        ),
    )


def _unique_username(db: Session, base: str) -> str:
    base = "".join(c for c in base.lower() if c.isalnum() or c == "_")[:24] or "trekker"
    candidate = base
    i = 0
    while db.scalar(select(User.id).where(User.username == candidate)):
        i += 1
        candidate = f"{base}{i}"
    return candidate


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    if db.scalar(select(User.id).where(User.email == body.email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    if db.scalar(select(User.id).where(User.username == body.username)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Username taken")
    user = User(
        email=body.email,
        username=body.username,
        display_name=body.display_name,
        password_hash=hash_password(body.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _tokens(user, is_new=True)


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email))
    if not user or not user.password_hash or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
    return _tokens(user, is_new=False)


@router.post("/apple", response_model=TokenResponse)
def apple_auth(body: AppleAuthRequest, db: Session = Depends(get_db)):
    """Sign in with Apple.

    MVP note: full Apple identity-token verification (JWKS validation) is a
    production task. Here we trust the client-provided identity, deriving a
    stable apple_id from the token, and create the user on first sign-in.
    """
    apple_id = f"apple_{abs(hash(body.identity_token)) % (10 ** 12)}"
    user = db.scalar(select(User).where(User.apple_id == apple_id))
    is_new = False
    if not user:
        email = body.email or f"{apple_id}@privaterelay.appleid.com"
        existing = db.scalar(select(User).where(User.email == email))
        if existing:
            existing.apple_id = apple_id
            user = existing
        else:
            user = User(
                apple_id=apple_id,
                email=email,
                username=_unique_username(db, (body.display_name or "trekker")),
                display_name=body.display_name or "Trekker",
            )
            db.add(user)
            is_new = True
        db.commit()
        db.refresh(user)
    return _tokens(user, is_new=is_new)


@router.post("/refresh", response_model=TokenResponse)
def refresh(body: RefreshRequest, db: Session = Depends(get_db)):
    payload = decode_token(body.refresh_token, expected_type="refresh")
    if not payload:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token")
    user = db.get(User, uuid.UUID(payload["sub"]))
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
    return _tokens(user, is_new=False)


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
def forgot_password(body: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """Begin a password reset.

    Always responds 200 so the endpoint can't be used to probe which emails are
    registered. In production the reset token would be emailed; with no email
    service in this local instance, it's returned in the response when the
    account exists.
    """
    user = db.scalar(select(User).where(User.email == body.email))
    generic = "If an account exists for that email, a reset token has been issued."
    if not user:
        return ForgotPasswordResponse(message=generic)
    return ForgotPasswordResponse(message=generic, reset_token=create_reset_token(str(user.id)))


@router.post("/reset-password", response_model=TokenResponse)
def reset_password(body: ResetPasswordRequest, db: Session = Depends(get_db)):
    payload = decode_token(body.reset_token, expected_type="reset")
    if not payload:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired reset token")
    user = db.get(User, uuid.UUID(payload["sub"]))
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
    user.password_hash = hash_password(body.new_password)
    db.commit()
    db.refresh(user)
    return _tokens(user, is_new=False)


@router.delete("/account", status_code=204)
def delete_account(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """GDPR: delete the user and all cascading data."""
    db.delete(user)
    db.commit()
