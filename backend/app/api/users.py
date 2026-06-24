from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, VisitedCountry, VisitedCity
from app.middleware.auth import get_current_user
from app.schemas.user import (
    UserProfile, UserPublic, UserUpdate, UserStats, UserMap, MapCountry, MapCity,
)
from app.services.stats import detailed_stats

router = APIRouter(prefix="/users", tags=["users"])


def _profile(user: User, include_email: bool = False) -> UserProfile:
    return UserProfile(
        id=str(user.id), username=user.username, display_name=user.display_name,
        avatar_url=user.avatar_url, bio=user.bio, home_city=user.home_city,
        home_country=user.home_country,
        email=user.email if include_email else None,
        total_countries=user.total_countries, total_cities=user.total_cities,
        total_km=float(user.total_km), total_trips=user.total_trips,
        current_streak=user.current_streak, longest_streak=user.longest_streak,
    )


def _get_by_username(db: Session, username: str) -> User:
    user = db.scalar(select(User).where(User.username == username))
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return user


@router.get("/me", response_model=UserProfile)
def get_me(user: User = Depends(get_current_user)):
    return _profile(user, include_email=True)


@router.patch("/me", response_model=UserProfile)
def update_me(body: UserUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    db.add(user)
    db.commit()
    db.refresh(user)
    return _profile(user, include_email=True)


@router.get("/search", response_model=list[UserPublic])
def search_users(q: str = Query(min_length=1), db: Session = Depends(get_db)):
    rows = db.execute(
        select(User).where(User.username.ilike(f"%{q}%")).limit(20)
    ).scalars().all()
    return [
        UserPublic(id=str(u.id), username=u.username, display_name=u.display_name,
                   avatar_url=u.avatar_url, bio=u.bio)
        for u in rows
    ]


@router.get("/{username}", response_model=UserProfile)
def get_user(username: str, db: Session = Depends(get_db)):
    return _profile(_get_by_username(db, username))


@router.get("/{username}/stats", response_model=UserStats)
def get_stats(username: str, db: Session = Depends(get_db)):
    user = _get_by_username(db, username)
    return UserStats(**detailed_stats(db, user))


@router.get("/{username}/map", response_model=UserMap)
def get_map(username: str, db: Session = Depends(get_db)):
    user = _get_by_username(db, username)
    countries = db.execute(
        select(VisitedCountry).where(VisitedCountry.user_id == user.id)
    ).scalars().all()
    cities = db.execute(
        select(VisitedCity).where(VisitedCity.user_id == user.id)
    ).scalars().all()
    return UserMap(
        countries=[
            MapCountry(code=c.country_code, name=c.country_name,
                       first_visited=c.first_visited, visits=c.visit_count)
            for c in countries
        ],
        cities=[
            MapCity(name=c.city_name, country_code=c.country_code,
                    lat=c.lat, lng=c.lng, visits=c.visit_count)
            for c in cities
        ],
    )
