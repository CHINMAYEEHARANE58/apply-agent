import os
from collections.abc import Generator
from pathlib import Path

# Bootstrap before importing the application: no developer cloud URL or
# provider credential may enter the test application's global configuration.
os.environ.update({
    "DATABASE_URL": "sqlite://", "DATABASE_DIRECT_URL": "",
    "AUTH_PROVIDER": "development", "APP_ENVIRONMENT": "test",
    "CLERK_SECRET_KEY": "", "CLERK_ISSUER": "", "CLERK_JWT_KEY": "",
    "APP_ENCRYPTION_KEY": "test-only-resume-encryption-secret-at-least-32-chars",
    "PRIVATE_RESUME_STORAGE_PATH": "/private/tmp/internagent-qa-private-resumes",
    "ALLOWED_ORIGINS": '["https://testserver"]',
})

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.config.database import Base, get_session
from app.config.settings import Settings, get_settings
from app.main import app
from app.resumes.storage import private_resume_storage
from app.security.http import RateLimitMiddleware

pytest_plugins = ["test_clerk_auth"]


@pytest.fixture(autouse=True)
def isolated_test_configuration(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    # A developer's Neon migration URL must never redirect SQLite tests to
    # their cloud database. Integration tests need a separate opt-in database.
    monkeypatch.setenv("DATABASE_URL", "sqlite://")
    monkeypatch.setenv("DATABASE_DIRECT_URL", "")
    monkeypatch.setenv("AUTH_PROVIDER", "development")
    monkeypatch.setenv("APP_ENVIRONMENT", "test")
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    @event.listens_for(engine, "connect")
    def sqlite_constraints(connection, _) -> None:
        connection.execute("PRAGMA foreign_keys=ON")
    Base.metadata.create_all(engine)
    test_session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    monkeypatch.setattr("app.scheduler.tasks.SessionLocal", test_session)
    original_storage_root = private_resume_storage.root
    monkeypatch.setenv("APP_ENVIRONMENT", "test")
    monkeypatch.setenv("AUTH_PROVIDER", "development")
    monkeypatch.setenv("APP_ENCRYPTION_KEY", "test-only-resume-encryption-secret-at-least-32-chars")
    get_settings.cache_clear()
    private_resume_storage.root = tmp_path / "private-resumes"

    def override_get_session() -> Generator[Session, None, None]:
        session = test_session()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_session] = override_get_session
    app.state.test_session_factory = test_session
    current = app.middleware_stack
    while current is not None:
        if isinstance(current, RateLimitMiddleware):
            current.requests.clear()
        current = getattr(current, "app", None)
    try:
        with TestClient(app, base_url="https://testserver") as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        del app.state.test_session_factory
        private_resume_storage.root = original_storage_root
        get_settings.cache_clear()
        Base.metadata.drop_all(engine)
        engine.dispose()
