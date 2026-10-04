from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.config.database import Base, get_session
from app.config.settings import get_settings
from app.main import app
from app.resumes.storage import private_resume_storage


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    test_session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    original_storage_root = private_resume_storage.root
    monkeypatch.setenv("APP_ENVIRONMENT", "test")
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
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        del app.state.test_session_factory
        private_resume_storage.root = original_storage_root
        get_settings.cache_clear()
        Base.metadata.drop_all(engine)
