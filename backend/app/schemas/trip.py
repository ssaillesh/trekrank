from datetime import date, datetime
from pydantic import BaseModel, Field


class TripCreate(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    origin_city: str | None = Field(default=None, max_length=100)
    origin_country: str | None = Field(default=None, min_length=2, max_length=2)
    dest_city: str = Field(max_length=100)
    dest_country: str = Field(min_length=2, max_length=2)
    transport_mode: str | None = Field(default=None, max_length=30)
    start_date: date
    end_date: date | None = None
    notes: str | None = None
    is_public: bool = True


class TripUpdate(BaseModel):
    title: str | None = None
    notes: str | None = None
    transport_mode: str | None = None
    is_public: bool | None = None
    origin_city: str | None = None
    origin_country: str | None = None
    dest_city: str | None = None
    dest_country: str | None = None
    start_date: date | None = None
    end_date: date | None = None


class PhotoOut(BaseModel):
    id: str
    photo_url: str
    thumbnail_url: str | None = None
    caption: str | None = None
    sort_order: int = 0


class TripOut(BaseModel):
    id: str
    user_id: str
    title: str | None = None
    notes: str | None = None
    transport_mode: str | None = None
    origin_city: str | None = None
    origin_country: str | None = None
    dest_city: str
    dest_country: str
    start_date: date
    end_date: date | None = None
    distance_km: float | None = None
    is_public: bool = True
    status: str = "processing"
    created_at: datetime
    photos: list[PhotoOut] = []


class TripList(BaseModel):
    items: list[TripOut]
    next_cursor: str | None = None


class BackfillTrip(BaseModel):
    dest_city: str
    dest_country: str = Field(min_length=2, max_length=2)
    start_date: date
    end_date: date | None = None
    origin_city: str | None = None
    origin_country: str | None = None
    transport_mode: str | None = None
    title: str | None = None


class BackfillRequest(BaseModel):
    trips: list[BackfillTrip]


class BackfillResponse(BaseModel):
    created: int
    processing: bool = True
    message: str
