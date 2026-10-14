from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.config.database import Base

if TYPE_CHECKING:
    from app.users.models import User


class UserSettings(Base):
    __tablename__ = "user_settings"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_user_settings_user_id"),
        CheckConstraint("minimum_match_score BETWEEN 0 AND 100", name="ck_settings_score"),
        CheckConstraint("max_daily_applications BETWEEN 0 AND 50", name="ck_settings_daily_limit"),
        CheckConstraint("maximum_jobs_evaluated_daily BETWEEN 0 AND 10000", name="ck_settings_job_limit"),
        CheckConstraint("maximum_applications_prepared_daily BETWEEN 0 AND 1000", name="ck_settings_prepare_limit"),
        CheckConstraint("application_mode IN ('review', 'batch', 'authorized-auto')", name="ck_settings_mode"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    search_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    search_time: Mapped[str | None] = mapped_column(String(8))
    timezone: Mapped[str] = mapped_column(String(64), default="UTC", nullable=False)
    maximum_jobs_evaluated_daily: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    maximum_applications_prepared_daily: Mapped[int] = mapped_column(Integer, default=20, nullable=False)
    enabled_sources: Mapped[list[str]] = mapped_column(JSON, default=lambda: ["catalog"], nullable=False)
    minimum_match_score: Mapped[int] = mapped_column(Integer, default=75, nullable=False)
    max_daily_applications: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    application_mode: Mapped[str] = mapped_column(String(32), default="review", nullable=False)
    email_notifications: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    application_notifications: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    user: Mapped[User] = relationship(back_populates="settings")
