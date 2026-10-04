from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.config.database import Base

if TYPE_CHECKING:
    from app.jobs.models import Job
    from app.resumes.models import Resume
    from app.users.models import User


class Application(Base):
    __tablename__ = "applications"
    __table_args__ = (
        UniqueConstraint("user_id", "job_id", name="uq_applications_user_job"),
        CheckConstraint("status IN ('discovered', 'matched', 'prepared', 'awaiting_approval', 'submitted', 'assessment', 'interview', 'rejected', 'offer', 'withdrawn')", name="ck_applications_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("jobs.id", ondelete="RESTRICT"), nullable=False, index=True)
    resume_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("resumes.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(32), default="discovered", nullable=False)
    cover_letter: Mapped[str | None] = mapped_column(Text)
    application_message: Mapped[str | None] = mapped_column(Text)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    external_application_id: Mapped[str | None] = mapped_column(String(255))
    user: Mapped[User] = relationship(back_populates="applications")
    job: Mapped[Job] = relationship(back_populates="applications")
    resume: Mapped[Resume | None] = relationship(back_populates="applications")
