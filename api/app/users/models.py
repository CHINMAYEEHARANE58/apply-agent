from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.config.database import Base

if TYPE_CHECKING:
    from app.applications.models import Application
    from app.audit.models import AuditEvent
    from app.jobs.models import JobMatch, UserJob
    from app.preferences.models import InternshipPreference
    from app.profiles.models import CandidateProfile
    from app.resumes.models import Resume
    from app.users.settings_models import UserSettings


class User(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("email", name="uq_users_email"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), index=True, nullable=False)
    clerk_user_id: Mapped[str | None] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(512))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    profile: Mapped[CandidateProfile | None] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    preference: Mapped[InternshipPreference | None] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    resumes: Mapped[list[Resume]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    matches: Mapped[list[JobMatch]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    applications: Mapped[list[Application]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    audit_events: Mapped[list[AuditEvent]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    settings: Mapped[UserSettings | None] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    user_jobs: Mapped[list[UserJob]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
