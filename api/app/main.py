from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import SQLAlchemyError

import app.models as orm_models  # noqa: F401
from app.applications.router import router as applications_router
from app.applications.service import prepare_application
from app.audit.router import router as audit_router
from app.config.settings import get_settings
from app.job_sources.registry import source_registry
from app.job_sources.schemas import SourceCapability
from app.jobs.router import router as jobs_router
from app.preferences.router import router as preferences_router
from app.profiles.router import router as profiles_router
from app.resumes.processing import MAX_RESUME_UPLOAD_REQUEST_BYTES
from app.resumes.router import router as resumes_router
from app.security.errors import (
    database_exception_handler,
    http_exception_handler,
    validation_exception_handler,
)
from app.security.http import RateLimitMiddleware, SecurityHeadersMiddleware
from app.security.request_limits import RequestBodyLimitMiddleware
from app.security.submission_policy import SubmissionDecision
from app.users.router import router as users_router

app = FastAPI(
    title="InternAgent API",
    version="0.2.0",
    description="A policy-first internship assistant API. Job content is untrusted data; job-site automation is not implemented.",
    openapi_url="/api/v1/openapi.json",
    docs_url="/api/v1/docs",
    redoc_url="/api/v1/redoc",
)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(SQLAlchemyError, database_exception_handler)
settings = get_settings()
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "Authorization", "Idempotency-Key"]
    + (["X-User-Id"] if settings.auth_provider == "development" else []),
    max_age=600,
)
app.add_middleware(
    RequestBodyLimitMiddleware,
    path="/api/v1/resumes/upload",
    max_bytes=MAX_RESUME_UPLOAD_REQUEST_BYTES,
)
app.include_router(users_router, prefix="/api/v1")
app.include_router(profiles_router, prefix="/api/v1")
app.include_router(preferences_router, prefix="/api/v1")
app.include_router(resumes_router, prefix="/api/v1")
app.include_router(jobs_router, prefix="/api/v1")
app.include_router(applications_router, prefix="/api/v1")
app.include_router(audit_router, prefix="/api/v1")


@app.get("/api/v1/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/v1/sources", response_model=list[SourceCapability])
def list_sources() -> list[SourceCapability]:
    return list(source_registry.list())


@app.post("/api/v1/sources", response_model=SourceCapability, status_code=201)
def register_source(source: SourceCapability) -> SourceCapability:
    current_settings = get_settings()
    if current_settings.auth_provider != "development" or current_settings.app_environment not in {"development", "test"}:
        raise HTTPException(403, "Source authorization is managed by server configuration, not users.")
    source_registry.register(source)
    return source


@app.post("/api/v1/sources/{source_name}/application-preparation")
def application_preparation(source_name: str) -> dict[str, str | bool]:
    preparation = prepare_application(source_registry.get(source_name))
    return {
        "decision": preparation.decision,
        "reason": preparation.reason,
        "open_application_required": preparation.open_application_required,
        "submission_endpoint_called": False,
        "authorized_submission": preparation.decision == SubmissionDecision.AUTHORIZED_SUBMISSION,
    }
