import uuid
from datetime import datetime, date

from sqlalchemy import String, Text, Integer, Numeric, Boolean, Date, DateTime, CHAR, Float, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# Coordinates are stored as plain lat/lng columns (WGS84); distances are
# computed in Python with a Haversine great-circle formula. This keeps the app
# portable across any PostgreSQL without requiring the PostGIS extension.


class Trip(Base):
    __tablename__ = "trips"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # flight | train | car | bus | boat | bike | walk | other
    transport_mode: Mapped[str | None] = mapped_column(String(30), nullable=True)

    # origin
    origin_city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    origin_country: Mapped[str | None] = mapped_column(CHAR(2), nullable=True)
    origin_coords = mapped_column(
        Geography(geometry_type="POINT", srid=4326, spatial_index=True), nullable=True
    )

    # destination
    dest_city: Mapped[str] = mapped_column(String(100), nullable=False)
    dest_country: Mapped[str] = mapped_column(CHAR(2), nullable=False, index=True)
    dest_coords = mapped_column(
        Geography(geometry_type="POINT", srid=4326, spatial_index=True), nullable=True
    )

    start_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    distance_km: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)

    is_public: Mapped[bool] = mapped_column(Boolean, default=True)

    # processing status: processing | done | failed  (not in spec but useful for the client)
    status: Mapped[str] = mapped_column(String(20), default="processing")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    photos: Mapped[list["TripPhoto"]] = relationship(
        back_populates="trip", cascade="all, delete-orphan", order_by="TripPhoto.sort_order"
    )


class TripPhoto(Base):
    __tablename__ = "trip_photos"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trip_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trips.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    photo_url: Mapped[str] = mapped_column(String(500), nullable=False)
    thumbnail_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    caption: Mapped[str | None] = mapped_column(String(300), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    trip: Mapped["Trip"] = relationship(back_populates="photos")
