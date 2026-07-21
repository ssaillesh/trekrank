import uuid
from datetime import datetime, date

from sqlalchemy import String, Text, Numeric, Boolean, Date, DateTime, CHAR, Float, ForeignKey, func
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
    origin_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    origin_lng: Mapped[float | None] = mapped_column(Float, nullable=True)

    # destination
    dest_city: Mapped[str] = mapped_column(String(100), nullable=False)
    dest_country: Mapped[str] = mapped_column(CHAR(2), nullable=False, index=True)
    dest_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    dest_lng: Mapped[float | None] = mapped_column(Float, nullable=True)

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

