from datetime import date
from pydantic import BaseModel, EmailStr, Field


class UserPublic(BaseModel):
    id: str
    username: str
    display_name: str
    avatar_url: str | None = None
    bio: str | None = None
    home_city: str | None = None
    home_country: str | None = None
    featured_badges: list[str] = []


class UserProfile(UserPublic):
    email: str | None = None
    total_countries: int = 0
    total_cities: int = 0
    total_km: float = 0
    total_trips: int = 0
    current_streak: int = 0
    longest_streak: int = 0


class FeaturedBadgesUpdate(BaseModel):
    # Up to 3 earned badge ids, in the order they should appear.
    badge_ids: list[str] = Field(default_factory=list, max_length=3)


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    display_name: str | None = Field(default=None, max_length=100)
    bio: str | None = Field(default=None, max_length=300)
    avatar_url: str | None = Field(default=None, max_length=500)
    home_city: str | None = Field(default=None, max_length=100)
    home_country: str | None = Field(default=None, min_length=2, max_length=2)


class TopCountry(BaseModel):
    code: str
    visits: int


class UserStats(BaseModel):
    user_id: str
    total_countries: int
    total_cities: int
    total_km: float
    total_trips: int
    current_streak: int
    longest_streak: int
    continents_visited: list[str]
    top_country: TopCountry | None = None
    transport_breakdown: dict[str, int]
    year_stats: dict[str, dict[str, float]]


class MapCountry(BaseModel):
    code: str
    name: str
    first_visited: date
    visits: int


class MapCity(BaseModel):
    name: str
    country_code: str
    lat: float | None = None
    lng: float | None = None
    visits: int


class UserMap(BaseModel):
    countries: list[MapCountry]
    cities: list[MapCity]
