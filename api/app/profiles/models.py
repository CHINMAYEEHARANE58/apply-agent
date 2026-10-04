from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.config.database import Base

if TYPE_CHECKING:
    from app.users.models import User


class CandidateProfile(Base):
    __tablename__ = "candidate_profiles"
    __table_args__ = (UniqueConstraint("user_id", name="uq_candidate_profiles_user_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(40))
    location: Mapped[str | None] = mapped_column(String(200))
    work_authorization: Mapped[str | None] = mapped_column(String(200))
    relocation_allowed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    linkedin_url: Mapped[str | None] = mapped_column(String(2048))
    github_url: Mapped[str | None] = mapped_column(String(2048))
    portfolio_url: Mapped[str | None] = mapped_column(String(2048))
    user: Mapped[User] = relationship(back_populates="profile")
