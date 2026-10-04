import hashlib
import hmac
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Any, cast

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status
from pydantic import ValidationError
from sqlalchemy import func, select, update
from sqlalchemy.engine import CursorResult

from app.auth.dependencies import CurrentUser, SessionDep
from app.config.schemas import Page
from app.profiles.models import CandidateProfile
from app.resumes.facts import GeneratedResumeBullet, ResumeFact, ResumeFactStore
from app.resumes.models import Resume, ResumeFactRecord
from app.resumes.processing import (
    MAX_RESUME_SIZE_BYTES,
    ResumeProcessingError,
    empty_structured_resume,
    process_resume_upload,
)
from app.resumes.schemas import (
    ResumeApprovalRead,
    ResumeFactRead,
    ResumeRead,
    ResumeVerificationRequest,
    TailoredResumeCreate,
    TailoredResumeUpdate,
)
from app.resumes.storage import private_resume_storage
from app.resumes.verification import ResumeVerificationResult, verify_generated_resume
from app.security.encryption import (
    decrypt_json,
    decrypt_text,
    encrypt_json,
    encrypt_text,
    sensitive_text_fingerprint,
)
from app.security.errors import not_found
from app.users.models import User

router = APIRouter(prefix="/resumes", tags=["resumes"])


def owned_resume_or_404(resume_id: uuid.UUID, user_id: uuid.UUID, session: SessionDep) -> Resume:
    resume = session.scalar(select(Resume).where(Resume.id == resume_id, Resume.user_id == user_id))
    if resume is None:
        raise not_found("Resume")
    return resume


def owned_resume_for_update_or_404(
    resume_id: uuid.UUID, user_id: uuid.UUID, session: SessionDep
) -> Resume:
    """Lock a mutable resume row for a state transition.

    PostgreSQL holds this lock through the approval transaction, preventing a
    concurrent PATCH from replacing the verified draft before approval commits.
    The approval path also uses a ciphertext compare-and-set so the invariant
    remains safe on engines without row-level ``FOR UPDATE`` support.
    """

    resume = session.scalar(
        select(Resume)
        .where(Resume.id == resume_id, Resume.user_id == user_id)
        .with_for_update()
    )
    if resume is None:
        raise not_found("Resume")
    return resume


def master_resume_or_404(resume_id: uuid.UUID, user_id: uuid.UUID, session: SessionDep) -> Resume:
    resume = owned_resume_or_404(resume_id, user_id, session)
    if resume.type != "master" or resume.source_of_truth_locked_at is None:
        raise HTTPException(status_code=409, detail="A locked master resume is required.")
    return resume


def immutable_master_error() -> HTTPException:
    return HTTPException(
        status_code=409,
        detail="Master resumes are immutable source-of-truth versions. Upload a new version instead.",
    )


async def read_limited_upload(upload: UploadFile) -> bytes:
    content = bytearray()
    try:
        while chunk := await upload.read(64 * 1024):
            content.extend(chunk)
            if len(content) > MAX_RESUME_SIZE_BYTES:
                raise ResumeProcessingError("file_too_large", "The uploaded resume must be 5 MB or smaller.")
    finally:
        await upload.close()
    return bytes(content)


def processing_http_error(error: ResumeProcessingError) -> HTTPException:
    return HTTPException(status_code=422, detail={"code": error.code, "message": error.message})


def next_master_version(user_id: uuid.UUID, session: SessionDep) -> tuple[int, uuid.UUID | None]:
    # Serialize version assignment per candidate.  PostgreSQL honors this row
    # lock; SQLite test databases safely ignore it while the partial unique
    # index still prevents duplicate master versions.
    session.scalar(select(User.id).where(User.id == user_id).with_for_update())
    previous = session.scalar(
        select(Resume)
        .where(Resume.user_id == user_id, Resume.type == "master")
        .order_by(Resume.version.desc())
        .limit(1)
    )
    if previous is None:
        return 1, None
    return previous.version + 1, previous.id


def candidate_profile_values(user_id: uuid.UUID, session: SessionDep) -> dict[str, Any] | None:
    profile = session.scalar(select(CandidateProfile).where(CandidateProfile.user_id == user_id))
    if profile is None:
        return None
    return {
        "full_name": profile.full_name,
        "phone": profile.phone,
        "location": profile.location,
        "work_authorization": profile.work_authorization,
        "relocation_allowed": profile.relocation_allowed,
        "linkedin_url": profile.linkedin_url,
        "github_url": profile.github_url,
        "portfolio_url": profile.portfolio_url,
    }


def _fact_crypto_purpose(
    *,
    user_id: uuid.UUID,
    resume_id: uuid.UUID,
    fact_id: uuid.UUID,
    category: str,
    source: str,
    confidence: Decimal | float,
    field: str,
) -> str:
    """Bind fact ciphertext and its integrity tag to all material fact fields."""

    return (
        f"user:{user_id}:resume:{resume_id}:fact:{fact_id}:category:{category}:"
        f"source:{source}:confidence:{_canonical_fact_confidence(confidence)}:{field}"
    )


def _canonical_fact_confidence(value: Decimal | float) -> str:
    return format(Decimal(str(value)).normalize(), "f")


def _decrypted_fact_text(record: ResumeFactRecord) -> str:
    text_purpose = _fact_crypto_purpose(
        user_id=record.user_id,
        resume_id=record.resume_id,
        fact_id=record.fact_id,
        category=record.category,
        source=record.source,
        confidence=record.confidence,
        field="text",
    )
    fingerprint_purpose = _fact_crypto_purpose(
        user_id=record.user_id,
        resume_id=record.resume_id,
        fact_id=record.fact_id,
        category=record.category,
        source=record.source,
        confidence=record.confidence,
        field="fingerprint",
    )
    try:
        decrypted_text = decrypt_text(record.text, purpose=text_purpose)
        expected_fingerprint = sensitive_text_fingerprint(
            decrypted_text, purpose=fingerprint_purpose
        )
    except (RuntimeError, ValueError) as error:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "resume_fact_integrity_failed",
                "message": "A stored resume fact cannot be verified.",
            },
        ) from error
    if not hmac.compare_digest(record.text_fingerprint, expected_fingerprint):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "resume_fact_integrity_failed",
                "message": "A stored resume fact cannot be verified.",
            },
        )
    return decrypted_text


def _resume_fact_from_record(record: ResumeFactRecord) -> ResumeFact:
    return ResumeFact.model_validate(
        {
            "fact_id": record.fact_id,
            "category": record.category,
            "text": _decrypted_fact_text(record),
            "source": record.source,
            "confidence": float(record.confidence),
        }
    )


def fact_store_for_source(source_resume: Resume, user_id: uuid.UUID, session: SessionDep) -> ResumeFactStore:
    records = list(
        session.scalars(
            select(ResumeFactRecord).where(
                ResumeFactRecord.resume_id == source_resume.id,
                ResumeFactRecord.user_id == user_id,
            )
        )
    )
    stored_facts = [_resume_fact_from_record(record) for record in records]
    profile_facts = ResumeFactStore.from_parsed_resume(
        empty_structured_resume(), candidate_profile_values(user_id, session)
    ).facts
    return ResumeFactStore([*stored_facts, *profile_facts])


def stored_generated_bullets(resume: Resume) -> list[GeneratedResumeBullet]:
    """Read the persisted content that an approval is allowed to approve.

    The caller cannot substitute a separate, benign payload during approval.
    Generated content and its evidence references are stored together on the
    tailored-resume version and are re-validated before every approval.
    """

    if resume.generated_bullets_encrypted is None:
        if resume.generated_bullets_json is not None:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "tailored_resume_data_integrity_failed",
                    "message": "The tailored resume contains unprotected generated content.",
                },
            )
        return []
    try:
        encrypted_payload = decrypt_json(
            resume.generated_bullets_encrypted,
            purpose=f"resume:{resume.id}:generated-bullets",
        )
        raw_bullets = encrypted_payload.get("generated_bullets")
        if not isinstance(raw_bullets, list):
            raise ValueError("Generated bullets are missing from the encrypted payload.")
        return [GeneratedResumeBullet.model_validate(raw_bullet) for raw_bullet in raw_bullets]
    except (RuntimeError, ValidationError, ValueError) as error:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "invalid_stored_generated_content",
                "message": "The tailored resume has invalid generated content and cannot be approved.",
            },
        ) from error


def verification_for_tailored_resume(
    tailored_resume: Resume,
    request: ResumeVerificationRequest,
    user_id: uuid.UUID,
    session: SessionDep,
    *,
    require_fact_references: bool,
) -> ResumeVerificationResult:
    if tailored_resume.type != "tailored" or tailored_resume.source_resume_id is None:
        raise HTTPException(status_code=409, detail="Only a tailored resume with a master source can be verified.")
    source_resume = master_resume_or_404(tailored_resume.source_resume_id, user_id, session)
    return verify_generated_resume(
        stored_generated_bullets(tailored_resume),
        fact_store_for_source(source_resume, user_id, session),
        minimum_fact_confidence=request.minimum_fact_confidence,
        require_fact_references=require_fact_references,
    )


def approve_tailored_resume_if_unchanged(
    tailored_resume: Resume, user_id: uuid.UUID, session: SessionDep
) -> None:
    """Persist approval only if the exact verified encrypted draft is current.

    The ciphertext has a random nonce on every draft write, so it safely acts
    as an opaque content revision. This closes the verify-then-approve race
    even on databases where ``SELECT FOR UPDATE`` is advisory or unsupported.
    """

    verified_ciphertext = tailored_resume.generated_bullets_encrypted
    if verified_ciphertext is None:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "tailored_resume_data_integrity_failed",
                "message": "The tailored resume is missing protected generated content.",
            },
        )
    now = datetime.now(UTC)
    result = cast(
        CursorResult[Any],
        session.execute(
            update(Resume)
            .where(
                Resume.id == tailored_resume.id,
                Resume.user_id == user_id,
                Resume.type == "tailored",
                Resume.generated_bullets_encrypted == verified_ciphertext,
            )
            .values(approval_status="approved", approved_at=now)
        ),
    )
    if result.rowcount != 1:
        session.rollback()
        raise HTTPException(
            status_code=409,
            detail={
                "code": "tailored_resume_changed_during_approval",
                "message": "The tailored resume changed during verification. Review and approve it again.",
            },
        )
    session.commit()
    session.refresh(tailored_resume)


def serialize_resume(resume: Resume) -> ResumeRead:
    serialized = ResumeRead.model_validate(resume).model_dump()
    serialized["parsed_resume_json"] = _decrypted_master_resume(resume)
    serialized["generated_bullets"] = stored_generated_bullets(resume)
    return ResumeRead.model_validate(serialized)


def _decrypted_master_resume(resume: Resume) -> dict[str, Any] | None:
    if resume.type != "master":
        return None
    if resume.parsed_resume_encrypted is None:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "resume_data_integrity_failed",
                "message": "The master resume is missing protected parsed data.",
            },
        )
    try:
        return decrypt_json(
            resume.parsed_resume_encrypted,
            purpose=f"resume:{resume.id}:parsed",
        )
    except (RuntimeError, ValueError) as error:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "resume_data_integrity_failed",
                "message": "The encrypted resume data cannot be verified.",
            },
        ) from error


@router.get("", response_model=Page[ResumeRead])
def list_resumes(current_user: CurrentUser, session: SessionDep, limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)) -> Page[ResumeRead]:
    statement = select(Resume).where(Resume.user_id == current_user.id).order_by(Resume.created_at.desc())
    total = session.scalar(select(func.count()).select_from(Resume).where(Resume.user_id == current_user.id)) or 0
    items = list(session.scalars(statement.limit(limit).offset(offset)))
    return Page(
        items=[serialize_resume(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/upload", response_model=ResumeRead, status_code=status.HTTP_201_CREATED)
async def upload_master_resume(
    file: Annotated[UploadFile, File(description="Master resume PDF or DOCX, maximum 5 MB")],
    current_user: CurrentUser,
    session: SessionDep,
) -> ResumeRead:
    filename = file.filename or ""
    content_type = file.content_type
    try:
        content = await read_limited_upload(file)
        processed = process_resume_upload(
            filename=filename,
            content_type=content_type,
            content=content,
        )
    except ResumeProcessingError as error:
        raise processing_http_error(error) from error

    try:
        fact_store = ResumeFactStore.from_parsed_resume(processed.structured_resume)
    except (ValidationError, ValueError) as error:
        error_code = (
            "resume_fact_limit_exceeded"
            if "more than" in str(error).lower()
            else "invalid_resume_facts"
        )
        raise HTTPException(
            status_code=422,
            detail={
                "code": error_code,
                "message": "The resume contains unsafe or unsupported fact data.",
            },
        ) from error

    resume_id = uuid.uuid4()
    version, supersedes_resume_id = next_master_version(current_user.id, session)
    try:
        encrypted_parsed_resume = encrypt_json(
            processed.structured_resume,
            purpose=f"resume:{resume_id}:parsed",
        )
        fact_records = []
        for fact in fact_store.facts:
            fact_id = uuid.uuid5(uuid.NAMESPACE_URL, f"internagent:{resume_id}:{fact.fact_id}")
            text_purpose = _fact_crypto_purpose(
                user_id=current_user.id,
                resume_id=resume_id,
                fact_id=fact_id,
                category=fact.category,
                source=fact.source,
                confidence=fact.confidence,
                field="text",
            )
            fingerprint_purpose = _fact_crypto_purpose(
                user_id=current_user.id,
                resume_id=resume_id,
                fact_id=fact_id,
                category=fact.category,
                source=fact.source,
                confidence=fact.confidence,
                field="fingerprint",
            )
            fact_records.append(
                ResumeFactRecord(
                    fact_id=fact_id,
                    resume_id=resume_id,
                    user_id=current_user.id,
                    category=fact.category,
                    text=encrypt_text(fact.text, purpose=text_purpose),
                    text_fingerprint=sensitive_text_fingerprint(
                        fact.text, purpose=fingerprint_purpose
                    ),
                    source=fact.source,
                    confidence=Decimal(str(fact.confidence)),
                )
            )
    except RuntimeError as error:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "resume_encryption_unavailable",
                "message": "Resume encryption is not available.",
            },
        ) from error
    try:
        storage_key = private_resume_storage.save(
            current_user.id, resume_id, processed.extension[1:], content
        )
    except RuntimeError as error:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "resume_storage_unavailable",
                "message": "Private resume storage is not available.",
            },
        ) from error
    now = datetime.now(UTC)
    resume = Resume(
        id=resume_id,
        user_id=current_user.id,
        type="master",
        file_reference=storage_key,
        parsed_resume_json=None,
        parsed_resume_encrypted=encrypted_parsed_resume,
        version=version,
        supersedes_resume_id=supersedes_resume_id,
        # The transaction locks this source-of-truth record only after its
        # extracted facts are inserted. No requester can observe the brief
        # unlocked state, and production DB triggers then reject later fact
        # injection or any master-resume update.
        source_of_truth_locked_at=None,
        original_filename=processed.filename,
        content_type=processed.content_type,
        byte_size=len(content),
        content_sha256=hashlib.sha256(content).hexdigest(),
        parser_status="completed",
        parser_started_at=now,
        parser_completed_at=now,
        approval_status="not_applicable",
    )
    try:
        session.add(resume)
        session.add_all(fact_records)
        session.flush()
        resume.source_of_truth_locked_at = now
        session.commit()
    except Exception:
        session.rollback()
        private_resume_storage.delete(storage_key)
        raise
    session.refresh(resume)
    return serialize_resume(resume)


@router.post("/tailored", response_model=ResumeRead, status_code=status.HTTP_201_CREATED)
def create_tailored_resume(
    payload: TailoredResumeCreate, current_user: CurrentUser, session: SessionDep
) -> ResumeRead:
    master_resume_or_404(payload.source_resume_id, current_user.id, session)
    resume_id = uuid.uuid4()
    try:
        encrypted_bullets = encrypt_json(
            {"generated_bullets": [bullet.model_dump(mode="json") for bullet in payload.generated_bullets]},
            purpose=f"resume:{resume_id}:generated-bullets",
        )
    except RuntimeError as error:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "resume_encryption_unavailable",
                "message": "Resume encryption is not available.",
            },
        ) from error
    resume = Resume(
        id=resume_id,
        user_id=current_user.id,
        type="tailored",
        file_reference=f"tailored/{resume_id}",
        parsed_resume_json=None,
        source_resume_id=payload.source_resume_id,
        version=1,
        parser_status="completed",
        approval_status="draft",
        generated_bullets_json=None,
        generated_bullets_encrypted=encrypted_bullets,
    )
    session.add(resume)
    session.commit()
    session.refresh(resume)
    return serialize_resume(resume)


@router.get("/{resume_id}", response_model=ResumeRead)
def get_resume(resume_id: uuid.UUID, current_user: CurrentUser, session: SessionDep) -> ResumeRead:
    return serialize_resume(owned_resume_or_404(resume_id, current_user.id, session))


@router.get("/{resume_id}/facts", response_model=Page[ResumeFactRead])
def list_resume_facts(resume_id: uuid.UUID, current_user: CurrentUser, session: SessionDep, limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0)) -> Page[ResumeFactRead]:
    owned_resume_or_404(resume_id, current_user.id, session)
    where = (ResumeFactRecord.resume_id == resume_id, ResumeFactRecord.user_id == current_user.id)
    total = session.scalar(select(func.count()).select_from(ResumeFactRecord).where(*where)) or 0
    items = list(session.scalars(select(ResumeFactRecord).where(*where).order_by(ResumeFactRecord.created_at).limit(limit).offset(offset)))
    return Page(
        items=[
            ResumeFactRead.model_validate(
                {
                    "fact_id": item.fact_id,
                    "resume_id": item.resume_id,
                    "user_id": item.user_id,
                    "category": item.category,
                    "text": _decrypted_fact_text(item),
                    "source": item.source,
                    "confidence": float(item.confidence),
                    "created_at": item.created_at,
                }
            )
            for item in items
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/{resume_id}/verify", response_model=ResumeVerificationResult)
def verify_tailored_resume(resume_id: uuid.UUID, payload: ResumeVerificationRequest, current_user: CurrentUser, session: SessionDep) -> ResumeVerificationResult:
    resume = owned_resume_or_404(resume_id, current_user.id, session)
    return verification_for_tailored_resume(resume, payload, current_user.id, session, require_fact_references=False)


@router.post("/{resume_id}/approve", response_model=ResumeApprovalRead)
def approve_tailored_resume(resume_id: uuid.UUID, payload: ResumeVerificationRequest, current_user: CurrentUser, session: SessionDep) -> ResumeApprovalRead:
    resume = owned_resume_for_update_or_404(resume_id, current_user.id, session)
    verification = verification_for_tailored_resume(resume, payload, current_user.id, session, require_fact_references=True)
    if not verification.approved:
        raise HTTPException(status_code=422, detail={"code": "resume_verification_failed", "message": "Generated resume content is not supported by known facts.", "details": verification.model_dump(mode="json")})
    approve_tailored_resume_if_unchanged(resume, current_user.id, session)
    return ResumeApprovalRead(resume=serialize_resume(resume), verification=verification)


@router.patch("/{resume_id}", response_model=ResumeRead)
def update_resume(
    resume_id: uuid.UUID, payload: TailoredResumeUpdate, current_user: CurrentUser, session: SessionDep
) -> ResumeRead:
    resume = owned_resume_for_update_or_404(resume_id, current_user.id, session)
    if resume.type == "master":
        raise immutable_master_error()
    try:
        resume.generated_bullets_encrypted = encrypt_json(
            {"generated_bullets": [bullet.model_dump(mode="json") for bullet in payload.generated_bullets]},
            purpose=f"resume:{resume.id}:generated-bullets",
        )
    except RuntimeError as error:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "resume_encryption_unavailable",
                "message": "Resume encryption is not available.",
            },
        ) from error
    resume.generated_bullets_json = None
    resume.approval_status = "draft"
    resume.approved_at = None
    session.commit()
    session.refresh(resume)
    return serialize_resume(resume)


@router.delete("/{resume_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_resume(resume_id: uuid.UUID, current_user: CurrentUser, session: SessionDep) -> None:
    resume = owned_resume_or_404(resume_id, current_user.id, session)
    if resume.type == "master":
        raise immutable_master_error()
    session.delete(resume)
    session.commit()
