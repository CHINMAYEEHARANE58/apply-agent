import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.config.database import get_session
from app.main import app


@pytest.fixture(scope="session")
def postgres_engine():
    value = os.environ.get("TEST_DATABASE_URL", "")
    if not value:
        pytest.fail("PostgreSQL integration tests require a dedicated TEST_DATABASE_URL; see QA_RUNBOOK.md")
    url = make_url(value)
    if url.host not in {"127.0.0.1", "localhost"} or not url.database or not url.database.startswith("internagent_test"):
        pytest.fail("Refusing any non-local or non-test database. Never use DATABASE_URL from .env here.")
    engine = create_engine(url, hide_parameters=True, pool_pre_ping=True)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "20261014_0007"
    yield engine
    engine.dispose()


@pytest.fixture
def pg_client(client: TestClient, postgres_engine, monkeypatch) -> Generator[TestClient, None, None]:
    # Outer transaction rolls back this case; route commits use savepoints.
    with postgres_engine.connect() as connection:
        transaction = connection.begin()
        factory = sessionmaker(bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False)
        def session_dependency() -> Generator[Session, None, None]:
            with factory() as session:
                yield session
        app.dependency_overrides[get_session] = session_dependency
        app.state.test_session_factory = factory
        monkeypatch.setattr("app.scheduler.tasks.SessionLocal", factory)
        yield client
        transaction.rollback()
