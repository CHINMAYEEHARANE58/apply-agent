from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session
from test_authorization_isolation import create_user, headers
from test_secure_resume_api import upload_master_resume

from alembic import command
from app.applications.models import Application
from app.config.settings import get_settings
from app.jobs.models import Job, UserJob
from app.preferences.models import InternshipPreference
from app.profiles.models import CandidateProfile
from app.resumes.storage import private_resume_storage
from app.users.models import User
from app.users.settings_models import UserSettings


def job_fixture() -> Job:
    key = uuid4().hex
    return Job(source="qa", external_job_id=key, job_url="https://example.com/qa", company="QA", title="Intern", description="Fixture", fingerprint=key * 2)


def test_postgres_schema_matches_models(postgres_engine, monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", postgres_engine.url.render_as_string(hide_password=False))
    monkeypatch.setenv("DATABASE_DIRECT_URL", "")
    get_settings.cache_clear()
    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    command.check(config)


@pytest.mark.parametrize("kind", ["email", "preference", "invalid-user", "invalid-resume"])
def test_database_constraints_cannot_be_bypassed_with_raw_orm_writes(postgres_engine, kind) -> None:
    with postgres_engine.connect() as connection:
        transaction = connection.begin()
        with Session(connection, join_transaction_mode="create_savepoint") as session:
            user = User(email=f"qa-{uuid4().hex}@example.com")
            session.add(user)
            session.flush()
            if kind == "email":
                session.add(User(email=user.email))
            elif kind == "preference":
                session.add_all([InternshipPreference(user_id=user.id), InternshipPreference(user_id=user.id)])
            elif kind == "invalid-user":
                session.add(CandidateProfile(user_id=uuid4(), full_name="Orphan"))
            else:
                job = job_fixture()
                session.add(job)
                session.flush()
                session.add(Application(user_id=user.id, job_id=job.id, resume_id=uuid4()))
            with pytest.raises(IntegrityError):
                session.flush()
            session.rollback()
        transaction.rollback()


def test_concurrent_duplicate_applications_have_exactly_one_record(postgres_engine) -> None:
    with Session(postgres_engine) as session:
        user, job = User(email=f"concurrent-{uuid4().hex}@example.com"), job_fixture()
        session.add_all([user, job])
        session.commit()
        user_id, job_id = user.id, job.id
    def attempt():
        with Session(postgres_engine) as session:
            session.add(Application(user_id=user_id, job_id=job_id, status="prepared"))
            try:
                session.commit()
                return "created"
            except IntegrityError:
                session.rollback()
                return "duplicate"
    try:
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: attempt(), range(4)))
        assert results.count("created") == 1 and results.count("duplicate") == 3
        with Session(postgres_engine) as session:
            assert len(list(session.scalars(select(Application).where(Application.user_id == user_id)))) == 1
    finally:
        with postgres_engine.begin() as connection:
            connection.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})
            connection.execute(text("DELETE FROM jobs WHERE id = :id"), {"id": job_id})


def test_postgres_api_resume_isolation_and_database_immutability(pg_client, postgres_engine) -> None:
    first = create_user(pg_client, "pg-owner@example.com")
    second = create_user(pg_client, "pg-other@example.com")
    resume = upload_master_resume(pg_client, first)
    assert pg_client.get(f'/api/v1/resumes/{resume["id"]}', headers=headers(second)).status_code == 404
    assert pg_client.get(f'/api/v1/resumes/{resume["id"]}/facts', headers=headers(second)).status_code == 404
    # Use the route fixture's connection/savepoint to reach the same transaction.
    from app.main import app
    with app.state.test_session_factory() as session:
        with pytest.raises(SQLAlchemyError):
            session.execute(text("UPDATE resumes SET original_filename='tampered.docx' WHERE id=:id"), {"id": UUID(str(resume["id"]))})
            session.flush()
        session.rollback()
    assert pg_client.get(f'/api/v1/resumes/{resume["id"]}', headers=headers(first)).json()["original_filename"] == "master-resume.docx"


def test_committed_profile_preferences_settings_jobs_and_application_survive_new_engine(postgres_engine) -> None:
    with Session(postgres_engine) as session:
        user, job = User(email=f"persistent-{uuid4().hex}@example.com"), job_fixture()
        session.add_all([user, job])
        session.flush()
        session.add_all([
            CandidateProfile(user_id=user.id, full_name="Test User A", city="Pune", country="India"),
            InternshipPreference(user_id=user.id, roles=["Software Engineering Intern", "Frontend Intern"], skills=["React", "JavaScript", "Node.js", "Python"], preferred_cities=["Pune", "Bengaluru"], min_duration=3, max_duration=6, duration_unit="months", minimum_stipend=20000, currency="INR", max_daily_applications=8),
            UserSettings(user_id=user.id, search_time="09:15", max_daily_applications=8),
            UserJob(user_id=user.id, job_id=job.id, saved=True),
            Application(user_id=user.id, job_id=job.id, status="prepared", cover_letter="Truthful QA cover letter"),
        ])
        session.commit()
        user_id, job_id = user.id, job.id
    replacement = create_engine(postgres_engine.url, hide_parameters=True)
    try:
        with Session(replacement) as session:
            assert session.scalar(select(CandidateProfile).where(CandidateProfile.user_id == user_id)).full_name == "Test User A"
            preference = session.scalar(select(InternshipPreference).where(InternshipPreference.user_id == user_id))
            assert preference.skills == ["React", "JavaScript", "Node.js", "Python"]
            assert preference.max_daily_applications == 8 and preference.minimum_stipend == 20000
            assert session.scalar(select(UserSettings).where(UserSettings.user_id == user_id)).search_time == "09:15"
            assert session.scalar(select(UserJob).where(UserJob.user_id == user_id)).saved
            assert session.scalar(select(Application).where(Application.user_id == user_id)).status == "prepared"
    finally:
        replacement.dispose()
        with postgres_engine.begin() as connection:
            connection.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})
            connection.execute(text("DELETE FROM jobs WHERE id = :id"), {"id": job_id})


def test_account_deletion_cascades_historical_resumes_and_private_files(pg_client) -> None:
    owner = create_user(pg_client, "pg-delete@example.com")
    for _ in range(2):
        upload_master_resume(pg_client, owner)
    assert len(list((private_resume_storage.root / owner).glob("*.docx"))) == 2
    assert pg_client.delete("/api/v1/users/me", headers=headers(owner)).status_code == 204
    assert not list((private_resume_storage.root / owner).glob("*.docx"))
