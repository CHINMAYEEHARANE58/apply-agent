from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.config import Config

from alembic import command
from app.config.settings import get_settings


def test_clerk_migration_preserves_existing_accounts_and_profiles(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    url = f"sqlite:///{tmp_path / 'migration.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("APP_ENCRYPTION_KEY", "test-only-migration-key-at-least-32-characters")
    get_settings.cache_clear()
    root = Path(__file__).resolve().parents[1]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    command.upgrade(config, "20261010_0005")
    engine = sa.create_engine(url)
    with engine.begin() as connection:
        connection.execute(sa.text("INSERT INTO users (id, email) VALUES (:id, :email)"), {"id": "a" * 32, "email": "legacy@example.com"})
        connection.execute(sa.text("INSERT INTO candidate_profiles (id, user_id, full_name, relocation_allowed) VALUES (:id, :user, 'Legacy Candidate', false)"), {"id": "b" * 32, "user": "a" * 32})
    command.upgrade(config, "head")
    with engine.connect() as connection:
        assert connection.scalar(sa.text("SELECT email FROM users")) == "legacy@example.com"
        assert connection.scalar(sa.text("SELECT clerk_user_id FROM users")) is None
        assert connection.scalar(sa.text("SELECT full_name FROM candidate_profiles")) == "Legacy Candidate"
        assert connection.scalar(sa.text("SELECT created_at FROM candidate_profiles")) is not None
        assert connection.scalar(sa.text("SELECT version_num FROM alembic_version")) == "20261010_0006"
    indexes = sa.inspect(engine).get_indexes("users")
    assert any(index["name"] == "ix_users_clerk_user_id" and index["unique"] for index in indexes)
    command.check(config)
    engine.dispose()
