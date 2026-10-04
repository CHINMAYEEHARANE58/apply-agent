from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, Uuid

from app.config.database import Base

if TYPE_CHECKING:
    from app.applications.models import Application
    from app.users.models import User


class Resume(Base):
    __tablename__ = "resumes"
    __table_args__ = (
        CheckConstraint("type IN ('master', 'tailored')", name="ck_resumes_type"),
        CheckConstraint("version >= 1", name="ck_resumes_version_positive"),
        CheckConstraint(
            "source_resume_id IS NULL OR type = 'tailored'",
            name="ck_resumes_source_resume_type",
        ),
        CheckConstraint(
            "supersedes_resume_id IS NULL OR type = 'master'",
            name="ck_resumes_supersedes_resume_type",
        ),
        CheckConstraint(
            "source_of_truth_locked_at IS NULL OR type = 'master'",
            name="ck_resumes_source_of_truth_lock_type",
        ),
        CheckConstraint(
            "source_resume_id IS NULL OR source_resume_id <> id",
            name="ck_resumes_source_resume_not_self",
        ),
        CheckConstraint(
            "supersedes_resume_id IS NULL OR supersedes_resume_id <> id",
            name="ck_resumes_supersedes_resume_not_self",
        ),
        CheckConstraint(
            "byte_size IS NULL OR (byte_size > 0 AND byte_size <= 5242880)",
            name="ck_resumes_byte_size_limit",
        ),
        CheckConstraint(
            "content_sha256 IS NULL OR length(content_sha256) = 64",
            name="ck_resumes_content_sha256_length",
        ),
        CheckConstraint(
            "original_filename IS NULL OR lower(original_filename) LIKE '%.pdf' "
            "OR lower(original_filename) LIKE '%.docx'",
            name="ck_resumes_supported_file_extension",
        ),
        CheckConstraint(
            "content_type IS NULL OR content_type IN ("
            "'application/pdf', "
            "'application/vnd.openxmlformats-officedocument.wordprocessingml.document'"
            ")",
            name="ck_resumes_supported_content_type",
        ),
        CheckConstraint(
            "original_filename IS NULL OR content_type IS NULL OR "
            "(lower(original_filename) LIKE '%.pdf' AND content_type = 'application/pdf') OR "
            "(lower(original_filename) LIKE '%.docx' AND "
            "content_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')",
            name="ck_resumes_filename_content_type_pair",
        ),
        CheckConstraint(
            "(original_filename IS NULL AND content_type IS NULL AND byte_size IS NULL "
            "AND content_sha256 IS NULL) OR "
            "(original_filename IS NOT NULL AND content_type IS NOT NULL AND byte_size IS NOT NULL "
            "AND content_sha256 IS NOT NULL)",
            name="ck_resumes_file_metadata_complete",
        ),
        CheckConstraint(
            "parser_status IN ('pending', 'processing', 'completed', 'failed', 'rejected')",
            name="ck_resumes_parser_status",
        ),
        CheckConstraint(
            "parser_completed_at IS NULL OR parser_started_at IS NOT NULL",
            name="ck_resumes_parser_completion_order",
        ),
        CheckConstraint(
            "approval_status IN ('draft', 'approved', 'not_applicable')",
            name="ck_resumes_approval_status",
        ),
        CheckConstraint(
            "generated_bullets_json IS NULL OR type = 'tailored'",
            name="ck_resumes_generated_bullets_type",
        ),
        CheckConstraint(
            "generated_bullets_encrypted IS NULL OR type = 'tailored'",
            name="ck_resumes_encrypted_generated_bullets_type",
        ),
        CheckConstraint(
            "type <> 'tailored' OR generated_bullets_json IS NULL",
            name="ck_resumes_tailored_bullets_encrypted",
        ),
        CheckConstraint(
            "parsed_resume_encrypted IS NULL OR type = 'master'",
            name="ck_resumes_encrypted_parsed_data_type",
        ),
        CheckConstraint(
            "type <> 'master' OR parsed_resume_json IS NULL",
            name="ck_resumes_master_parsed_data_encrypted",
        ),
        Index(
            "uq_resumes_user_master_version",
            "user_id",
            "version",
            unique=True,
            postgresql_where=text("type = 'master'"),
            sqlite_where=text("type = 'master'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    file_reference: Mapped[str] = mapped_column(String(512), nullable=False)
    parsed_resume_json: Mapped[dict[str, Any] | None] = mapped_column(JSON(none_as_null=True))
    parsed_resume_encrypted: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(default=1, nullable=False)
    source_resume_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("resumes.id", ondelete="SET NULL")
    )
    supersedes_resume_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("resumes.id", ondelete="SET NULL")
    )
    source_of_truth_locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    original_filename: Mapped[str | None] = mapped_column(String(255))
    content_type: Mapped[str | None] = mapped_column(String(128))
    byte_size: Mapped[int | None] = mapped_column(Integer)
    content_sha256: Mapped[str | None] = mapped_column(String(64))
    parser_status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    parser_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    parser_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    parser_error: Mapped[str | None] = mapped_column(Text)
    approval_status: Mapped[str] = mapped_column(String(32), default="not_applicable", nullable=False)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Legacy compatibility column only. New tailored content is written to
    # generated_bullets_encrypted; SQL NULL (not JSON ``null``) is required
    # by the plaintext-prohibition constraint.
    generated_bullets_json: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSON(none_as_null=True)
    )
    generated_bullets_encrypted: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    user: Mapped[User] = relationship(back_populates="resumes")
    applications: Mapped[list[Application]] = relationship(back_populates="resume")
    facts: Mapped[list[ResumeFactRecord]] = relationship(back_populates="resume", cascade="all, delete-orphan")


class ResumeFactRecord(Base):
    __tablename__ = "resume_facts"
    __table_args__ = (
        UniqueConstraint(
            "resume_id",
            "category",
            "source",
            "text_fingerprint",
            name="uq_resume_facts_resume_category_source_text",
        ),
        CheckConstraint(
            "category IN ('contact', 'summary', 'education', 'experience', 'internships', "
            "'projects', 'skills', 'certifications', 'achievements', 'links', "
            "'candidate_profile')",
            name="ck_resume_facts_category",
        ),
        CheckConstraint(
            "source IN ('master_resume', 'candidate_profile')",
            name="ck_resume_facts_source",
        ),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_resume_facts_confidence"),
        CheckConstraint("length(trim(text)) > 0", name="ck_resume_facts_text_nonempty"),
    )

    fact_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    resume_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    # The encrypted value is written and read by the resume service so its
    # authenticated associated data can bind it to this precise fact, resume,
    # and user. A static ORM encryption type would permit ciphertext swaps
    # between records that share the same key.
    text: Mapped[str] = mapped_column(Text, nullable=False)
    text_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    resume: Mapped[Resume] = relationship(back_populates="facts")
