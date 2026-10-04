from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, Uuid

from app.config.database import Base

if TYPE_CHECKING:
    from app.applications.models import Application
    from app.users.models import User


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("source", "external_job_id", name="uq_jobs_source_external_id"),
        UniqueConstraint("fingerprint", name="uq_jobs_fingerprint"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    external_job_id: Mapped[str] = mapped_column(String(255), nullable=False)
    job_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    company: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    location: Mapped[str | None] = mapped_column(String(200))
    workplace_type: Mapped[str | None] = mapped_column(String(32))
    duration: Mapped[str | None] = mapped_column(String(100))
    stipend: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    currency: Mapped[str | None] = mapped_column(String(3))
    skills: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(128), nullable=False)
    matches: Mapped[list[JobMatch]] = relationship(back_populates="job", cascade="all, delete-orphan")
    applications: Mapped[list[Application]] = relationship(back_populates="job")


class JobMatch(Base):
    __tablename__ = "job_matches"
    __table_args__ = (
        UniqueConstraint("user_id", "job_id", name="uq_job_matches_user_job"),
        CheckConstraint("score >= 0 AND score <= 100", name="ck_job_matches_score"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    hard_filter_passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    matched_skills: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    missing_skills: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    user: Mapped[User] = relationship(back_populates="matches")
    job: Mapped[Job] = relationship(back_populates="matches")
