from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, Uuid

from app.config.database import Base

if TYPE_CHECKING:
    from app.users.models import User


class InternshipPreference(Base):
    __tablename__ = "internship_preferences"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_internship_preferences_user_id"),
        CheckConstraint(
            "min_duration IS NULL OR max_duration IS NULL OR min_duration <= max_duration",
            name="ck_preferences_duration_range",
        ),
        CheckConstraint("max_daily_applications >= 0", name="ck_preferences_daily_limit"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    roles: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    skills: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    preferred_locations: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    preferred_countries: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    preferred_states: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    preferred_cities: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    remote_allowed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    hybrid_allowed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    onsite_allowed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    min_duration: Mapped[int | None] = mapped_column(Integer)
    max_duration: Mapped[int | None] = mapped_column(Integer)
    duration_unit: Mapped[str] = mapped_column(String(16), default="weeks", nullable=False)
    minimum_stipend: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    currency: Mapped[str | None] = mapped_column(String(3))
    allow_unpaid: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    earliest_start_date: Mapped[date | None] = mapped_column(Date)
    latest_start_date: Mapped[date | None] = mapped_column(Date)
    preferred_industries: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    preferred_companies: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    excluded_companies: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    excluded_keywords: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    max_daily_applications: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    application_mode: Mapped[str] = mapped_column(String(32), default="review", nullable=False)
    minimum_match_score: Mapped[int] = mapped_column(Integer, default=75, nullable=False)
    search_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    preferred_search_time: Mapped[str | None] = mapped_column(String(8))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    user: Mapped[User] = relationship(back_populates="preference")
