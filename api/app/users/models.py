from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.config.database import Base

if TYPE_CHECKING:
    from app.applications.models import Application
    from app.audit.models import AuditEvent
    from app.jobs.models import JobMatch
    from app.preferences.models import InternshipPreference
    from app.profiles.models import CandidateProfile
    from app.resumes.models import Resume


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    profile: Mapped[CandidateProfile | None] = relationship(back_populates="user", cascade="all, delete-orphan")
    preference: Mapped[InternshipPreference | None] = relationship(back_populates="user", cascade="all, delete-orphan")
    resumes: Mapped[list[Resume]] = relationship(back_populates="user", cascade="all, delete-orphan")
    matches: Mapped[list[JobMatch]] = relationship(back_populates="user", cascade="all, delete-orphan")
    applications: Mapped[list[Application]] = relationship(back_populates="user", cascade="all, delete-orphan")
    audit_events: Mapped[list[AuditEvent]] = relationship(back_populates="user", cascade="all, delete-orphan")
