import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from app.config.schemas import APIModel
from app.resumes.facts import GeneratedResumeBullet, ResumeFact
from app.resumes.verification import ResumeVerificationResult

ResumeType = Literal["master", "tailored"]
ParserStatus = Literal["pending", "processing", "completed", "failed", "rejected"]
ApprovalStatus = Literal["draft", "approved", "not_applicable"]


class ResumeFactRead(ResumeFact):
    resume_id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime


class ResumeRead(APIModel):
    id: uuid.UUID
    user_id: uuid.UUID
    type: ResumeType
    version: int
    source_resume_id: uuid.UUID | None = None
    supersedes_resume_id: uuid.UUID | None = None
    source_of_truth_locked_at: datetime | None = None
    original_filename: str | None = None
    content_type: str | None = None
    byte_size: int | None = None
    content_sha256: str | None = None
    parsed_resume_json: dict[str, Any] | None = None
    parser_status: ParserStatus
    parser_started_at: datetime | None = None
    parser_completed_at: datetime | None = None
    approval_status: ApprovalStatus
    approved_at: datetime | None = None
    generated_bullets: list[GeneratedResumeBullet] | None = None
    created_at: datetime


class TailoredResumeCreate(APIModel):
    source_resume_id: uuid.UUID
    generated_bullets: list[GeneratedResumeBullet] = Field(min_length=1, max_length=200)


class TailoredResumeUpdate(APIModel):
    generated_bullets: list[GeneratedResumeBullet] = Field(min_length=1, max_length=200)


class ResumeVerificationRequest(APIModel):
    # Callers may require more evidence, but cannot lower the policy floor for
    # preview or approval of a tailored resume.
    minimum_fact_confidence: float = Field(default=0.8, ge=0.8, le=1)


class ResumeApprovalRead(APIModel):
    resume: ResumeRead
    verification: ResumeVerificationResult
