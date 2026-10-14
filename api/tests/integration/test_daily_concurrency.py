import hashlib
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session
from test_secure_resume_api import docx_resume_payload

from app.applications.models import Application
from app.jobs.models import Job
from app.preferences.models import InternshipPreference
from app.resumes.models import Resume, ResumeFactRecord
from app.resumes.processing import DOCX_MIME_TYPE, process_resume_upload
from app.resumes.router import _fact_crypto_purpose
from app.resumes.storage import PrivateResumeStorage
from app.scheduler.pipeline import run_daily_search
from app.scheduler.run_models import DailySearchRun
from app.security.encryption import encrypt_json, encrypt_text, sensitive_text_fingerprint
from app.users.models import User


def test_postgres_concurrent_daily_workers_and_restart_prepare_only_one_package(postgres_engine, tmp_path):
    with Session(postgres_engine) as session:
        user = User(email=f"daily-concurrency-{uuid4().hex}@example.com")
        job = Job(source="manual", external_job_id=uuid4().hex, job_url="https://example.com/internship", company="Concurrency QA", title="Software Intern", description="Python internship", workplace_type="remote", skills=["Python"], fingerprint=uuid4().hex * 2)
        session.add_all([user, job])
        session.flush()
        user_id, job_id = user.id, job.id
        resume_id, fact_id = uuid4(), uuid4()
        session.add(InternshipPreference(user_id=user_id, roles=["Software Intern"], minimum_match_score=0))
        content = docx_resume_payload()
        parsed = process_resume_upload(filename="master.docx", content_type=DOCX_MIME_TYPE, content=content)
        storage = PrivateResumeStorage(tmp_path / "private-resumes")
        reference = storage.save(user_id, resume_id, "docx", content)
        now = datetime.now(UTC)
        master = Resume(id=resume_id, user_id=user_id, type="master", file_reference=reference, parser_status="completed", parser_started_at=now, parser_completed_at=now, source_of_truth_locked_at=None, original_filename="master.docx", content_type=DOCX_MIME_TYPE, byte_size=len(content), content_sha256=hashlib.sha256(content).hexdigest(), parsed_resume_encrypted=encrypt_json(parsed.structured_resume, purpose=f"resume:{resume_id}:parsed"))
        session.add(master)
        fields = dict(user_id=user_id, resume_id=resume_id, fact_id=fact_id, category="skills", source="master_resume", confidence=Decimal("1"))
        session.add(ResumeFactRecord(**fields, text=encrypt_text("Python", purpose=_fact_crypto_purpose(**fields, field="text")), text_fingerprint=sensitive_text_fingerprint("Python", purpose=_fact_crypto_purpose(**fields, field="fingerprint"))))
        session.flush()
        master.source_of_truth_locked_at = now
        session.commit()
    def execute(_):
        with Session(postgres_engine) as session:
            return run_daily_search(session, user_id)
    try:
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(execute, range(4)))
        assert [result["status"] for result in results].count("completed") == 1
        assert [result["status"] for result in results].count("already_completed") == 3
        assert sum(result["applications_prepared"] for result in results) == 1
        with Session(postgres_engine) as session:
            assert session.scalar(select(func.count()).select_from(Application).where(Application.user_id == user_id)) == 1
            assert session.scalar(select(func.count()).select_from(DailySearchRun).where(DailySearchRun.user_id == user_id)) == 1
        # New sessions represent fresh processes; idempotency is not memory-based.
        assert execute(None)["applications_prepared"] == 0
    finally:
        with postgres_engine.begin() as connection:
            connection.execute(text("DELETE FROM users WHERE id=:id"), {"id": user_id})
            connection.execute(text("DELETE FROM jobs WHERE id=:id"), {"id": job_id})


def test_owned_object_validation_rejects_namespace_traversal(tmp_path):
    import pytest
    owner, other = uuid4(), uuid4()
    storage = PrivateResumeStorage(tmp_path)
    with pytest.raises(ValueError):
        storage.owned_path(f"{owner}/../{other}/{uuid4()}.pdf", owner)
