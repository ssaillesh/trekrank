import uuid
from datetime import date

from sqlalchemy import String, Integer, Date, CHAR, Float, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class VisitedCountry(Base):
    __tablename__ = "visited_countries"
    __table_args__ = (
        UniqueConstraint("user_id", "country_code", name="uq_visited_country"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    country_code: Mapped[str] = mapped_column(CHAR(2), nullable=False)
    country_name: Mapped[str] = mapped_column(String(100), nullable=False)
    first_visited: Mapped[date] = mapped_column(Date, nullable=False)
    visit_count: Mapped[int] = mapped_column(Integer, default=1)


class VisitedCity(Base):
    __tablename__ = "visited_cities"
    __table_args__ = (
        UniqueConstraint("user_id", "city_name", "country_code", name="uq_visited_city"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    city_name: Mapped[str] = mapped_column(String(100), nullable=False)
    country_code: Mapped[str] = mapped_column(CHAR(2), nullable=False)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    first_visited: Mapped[date] = mapped_column(Date, nullable=False)
    visit_count: Mapped[int] = mapped_column(Integer, default=1)
