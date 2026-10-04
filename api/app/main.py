from fastapi import FastAPI

from app.applications.service import prepare_application
from app.job_sources.registry import source_registry
from app.job_sources.schemas import SourceCapability
from app.security.submission_policy import SubmissionDecision

app = FastAPI(title="InternAgent API", version="0.1.0")


@app.get("/api/v1/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/v1/sources", response_model=list[SourceCapability])
def list_sources() -> list[SourceCapability]:
    return list(source_registry.list())


@app.post("/api/v1/sources", response_model=SourceCapability, status_code=201)
def register_source(source: SourceCapability) -> SourceCapability:
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
