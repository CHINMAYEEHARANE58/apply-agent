from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.config import Config
from sqlalchemy.exc import IntegrityError

from alembic import command
from app.config.settings import get_settings
from app.security.encryption import decrypt_json, encrypt_json

API_ROOT = Path(__file__).resolve().parents[1]


def alembic_config(database_url: str) -> Config:
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(API_ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def migrate_to_0002(monkeypatch: pytest.MonkeyPatch, database_url: str) -> Config:
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("APP_ENCRYPTION_KEY", "test-only-resume-encryption-secret-at-least-32-chars")
    get_settings.cache_clear()
    config = alembic_config(database_url)
    command.upgrade(config, "20261004_0002")
    return config


def migrate_to_0003(monkeypatch: pytest.MonkeyPatch, database_url: str) -> Config:
    config = migrate_to_0002(monkeypatch, database_url)
    command.upgrade(config, "20261004_0003")
    return config


def legacy_tables() -> tuple[sa.Table, sa.Table]:
    metadata = sa.MetaData()
    users = sa.Table(
        "users",
        metadata,
        sa.Column("id", sa.Uuid()),
        sa.Column("email", sa.String()),
    )
    resumes = sa.Table(
        "resumes",
        metadata,
        sa.Column("id", sa.Uuid()),
        sa.Column("user_id", sa.Uuid()),
        sa.Column("type", sa.String()),
        sa.Column("file_reference", sa.String()),
        sa.Column("parsed_resume_json", sa.JSON()),
        sa.Column("parsed_resume_encrypted", sa.Text()),
        sa.Column("generated_bullets_json", sa.JSON()),
        sa.Column("generated_bullets_encrypted", sa.Text()),
        sa.Column("version", sa.Integer()),
        sa.Column("parser_status", sa.String()),
        sa.Column("approval_status", sa.String()),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
    )
    return users, resumes


def seed_legacy_master_resume(engine: sa.Engine, *, parsed_resume_json: object) -> uuid.UUID:
    users, resumes = legacy_tables()
    user_id = uuid.uuid4()
    resume_id = uuid.uuid4()
    with engine.begin() as connection:
        connection.execute(users.insert().values(id=user_id, email=f"{user_id}@example.test"))
        connection.execute(
            resumes.insert().values(
                id=resume_id,
                user_id=user_id,
                type="master",
                file_reference=f"legacy/{resume_id}",
                parsed_resume_json=parsed_resume_json,
                parsed_resume_encrypted=None,
                version=1,
                parser_status="pending",
                approval_status="draft",
            )
        )
    return resume_id


def read_raw_resume(engine: sa.Engine) -> sa.RowMapping:
    with engine.connect() as connection:
        return connection.execute(
            sa.text("SELECT parsed_resume_json, parsed_resume_encrypted FROM resumes")
        ).mappings().one()


def seed_legacy_tailored_resume(
    engine: sa.Engine,
    *,
    generated_bullets_json: object,
    generated_bullets_encrypted: str | None = None,
    approval_status: str = "draft",
    approved_at: datetime | None = None,
) -> uuid.UUID:
    users, resumes = legacy_tables()
    user_id = uuid.uuid4()
    resume_id = uuid.uuid4()
    with engine.begin() as connection:
        connection.execute(users.insert().values(id=user_id, email=f"{user_id}@example.test"))
        connection.execute(
            resumes.insert().values(
                id=resume_id,
                user_id=user_id,
                type="tailored",
                file_reference=f"tailored/{resume_id}",
                generated_bullets_json=generated_bullets_json,
                generated_bullets_encrypted=generated_bullets_encrypted,
                version=1,
                parser_status="completed",
                approval_status=approval_status,
                approved_at=approved_at,
            )
        )
    return resume_id


def read_raw_tailored_resume(engine: sa.Engine) -> sa.RowMapping:
    with engine.connect() as connection:
        return connection.execute(
            sa.text(
                "SELECT generated_bullets_json, generated_bullets_encrypted, approval_status, approved_at "
                "FROM resumes WHERE type = 'tailored'"
            )
        ).mappings().one()


def raw_json_value(value: object) -> object:
    return json.loads(value) if isinstance(value, str) else value


def test_legacy_master_resume_json_is_encrypted_before_plaintext_is_prohibited(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_url = f"sqlite:///{tmp_path / 'legacy-resume.db'}"
    config = migrate_to_0002(monkeypatch, database_url)
    engine = sa.create_engine(database_url)
    legacy_json = {"summary": "Built FastAPI services at Acme.", "skills": ["Python"]}
    resume_id = seed_legacy_master_resume(engine, parsed_resume_json=legacy_json)

    command.upgrade(config, "head")

    migrated = read_raw_resume(engine)
    assert migrated["parsed_resume_json"] is None
    ciphertext = migrated["parsed_resume_encrypted"]
    assert isinstance(ciphertext, str)
    assert ciphertext.startswith("internagent:v1:")
    assert "FastAPI" not in ciphertext
    assert decrypt_json(ciphertext, purpose=f"resume:{resume_id}:parsed") == legacy_json

    _, resumes = legacy_tables()
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(
                resumes.insert().values(
                    id=uuid.uuid4(),
                    user_id=uuid.uuid4(),
                    type="master",
                    file_reference="legacy/new-master",
                    parsed_resume_json={"skills": ["fabricated"]},
                    version=1,
                    parser_status="pending",
                    approval_status="draft",
                )
            )


def test_backfill_stops_without_clearing_plaintext_when_encryption_key_is_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_url = f"sqlite:///{tmp_path / 'missing-key.db'}"
    config = migrate_to_0002(monkeypatch, database_url)
    engine = sa.create_engine(database_url)
    legacy_json = {"summary": "Candidate-provided legacy data."}
    seed_legacy_master_resume(engine, parsed_resume_json=legacy_json)

    monkeypatch.delenv("APP_ENCRYPTION_KEY")
    get_settings.cache_clear()
    with pytest.raises(RuntimeError, match="APP_ENCRYPTION_KEY"):
        command.upgrade(config, "head")

    raw = read_raw_resume(engine)
    assert raw_json_value(raw["parsed_resume_json"]) == legacy_json
    assert raw["parsed_resume_encrypted"] is None
    with engine.connect() as connection:
        assert connection.scalar(sa.text("SELECT version_num FROM alembic_version")) == "20261004_0002"


def test_backfill_stops_without_clearing_malformed_legacy_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_url = f"sqlite:///{tmp_path / 'malformed-legacy.db'}"
    config = migrate_to_0002(monkeypatch, database_url)
    engine = sa.create_engine(database_url)
    seed_legacy_master_resume(engine, parsed_resume_json=["not", "a", "resume", "object"])

    with pytest.raises(RuntimeError, match="malformed"):
        command.upgrade(config, "head")

    raw = read_raw_resume(engine)
    assert raw_json_value(raw["parsed_resume_json"]) == ["not", "a", "resume", "object"]
    assert raw["parsed_resume_encrypted"] is None


def test_sql_only_rendering_fails_closed_for_encrypted_data_backfill(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = "postgresql+psycopg://internagent:local@localhost:5432/internagent"
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("APP_ENCRYPTION_KEY", "test-only-resume-encryption-secret-at-least-32-chars")
    get_settings.cache_clear()

    with pytest.raises(RuntimeError, match="offline SQL output is intentionally unsupported"):
        command.upgrade(alembic_config(database_url), "head", sql=True)


def test_sql_only_rendering_fails_closed_for_tailored_bullet_backfill(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = "postgresql+psycopg://internagent:local@localhost:5432/internagent"
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("APP_ENCRYPTION_KEY", "test-only-resume-encryption-secret-at-least-32-chars")
    get_settings.cache_clear()

    with pytest.raises(RuntimeError, match="offline SQL output is intentionally unsupported"):
        command.upgrade(
            alembic_config(database_url),
            "20261004_0003:20261004_0004",
            sql=True,
        )


def test_legacy_tailored_bullets_are_encrypted_before_plaintext_is_prohibited(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_url = f"sqlite:///{tmp_path / 'legacy-tailored-resume.db'}"
    config = migrate_to_0003(monkeypatch, database_url)
    engine = sa.create_engine(database_url)
    legacy_bullets = [
        {
            "text": "Built FastAPI services at Acme.",
            "supporting_fact_ids": [str(uuid.uuid4())],
        }
    ]
    resume_id = seed_legacy_tailored_resume(
        engine,
        generated_bullets_json=legacy_bullets,
        approval_status="approved",
        approved_at=datetime.now(UTC),
    )

    command.upgrade(config, "head")

    migrated = read_raw_tailored_resume(engine)
    assert migrated["generated_bullets_json"] is None
    ciphertext = migrated["generated_bullets_encrypted"]
    assert isinstance(ciphertext, str)
    assert ciphertext.startswith("internagent:v1:")
    assert "FastAPI" not in ciphertext
    assert decrypt_json(
        ciphertext,
        purpose=f"resume:{resume_id}:generated-bullets",
    ) == {
        "generated_bullets": [
            {
                "text": "Built FastAPI services at Acme.",
                "supporting_fact_ids": legacy_bullets[0]["supporting_fact_ids"],
            }
        ]
    }
    assert migrated["approval_status"] == "draft"
    assert migrated["approved_at"] is None

    users, resumes = legacy_tables()
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            existing_user_id = connection.scalar(sa.select(users.c.id).limit(1))
            connection.execute(
                resumes.insert().values(
                    id=uuid.uuid4(),
                    user_id=existing_user_id,
                    type="tailored",
                    file_reference="tailored/plaintext-should-fail",
                    generated_bullets_json=legacy_bullets,
                    version=1,
                    parser_status="completed",
                    approval_status="draft",
                )
            )


def test_tailored_bullet_backfill_stops_without_clearing_malformed_plaintext(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_url = f"sqlite:///{tmp_path / 'malformed-tailored-resume.db'}"
    config = migrate_to_0003(monkeypatch, database_url)
    engine = sa.create_engine(database_url)
    malformed_bullets = [{"supporting_fact_ids": []}]
    seed_legacy_tailored_resume(engine, generated_bullets_json=malformed_bullets)

    with pytest.raises(RuntimeError, match="bullets are malformed"):
        command.upgrade(config, "head")

    raw = read_raw_tailored_resume(engine)
    assert raw_json_value(raw["generated_bullets_json"]) == malformed_bullets
    assert raw["generated_bullets_encrypted"] is None
    with engine.connect() as connection:
        assert connection.scalar(sa.text("SELECT version_num FROM alembic_version")) == "20261004_0003"


def test_tailored_bullet_backfill_requires_an_encryption_key_before_clearing_plaintext(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_url = f"sqlite:///{tmp_path / 'missing-key-tailored-resume.db'}"
    config = migrate_to_0003(monkeypatch, database_url)
    engine = sa.create_engine(database_url)
    legacy_bullets = [{"text": "Candidate-provided tailored content."}]
    seed_legacy_tailored_resume(engine, generated_bullets_json=legacy_bullets)

    monkeypatch.delenv("APP_ENCRYPTION_KEY")
    get_settings.cache_clear()
    with pytest.raises(RuntimeError, match="APP_ENCRYPTION_KEY"):
        command.upgrade(config, "head")

    raw = read_raw_tailored_resume(engine)
    assert raw_json_value(raw["generated_bullets_json"]) == legacy_bullets
    assert raw["generated_bullets_encrypted"] is None
    with engine.connect() as connection:
        assert connection.scalar(sa.text("SELECT version_num FROM alembic_version")) == "20261004_0003"


def test_tailored_bullet_backfill_resets_all_legacy_approvals(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_url = f"sqlite:///{tmp_path / 'approved-tailored-resume.db'}"
    config = migrate_to_0003(monkeypatch, database_url)
    engine = sa.create_engine(database_url)
    seed_legacy_tailored_resume(
        engine,
        generated_bullets_json=None,
        approval_status="approved",
        approved_at=datetime.now(UTC),
    )

    command.upgrade(config, "head")

    migrated = read_raw_tailored_resume(engine)
    assert migrated["generated_bullets_json"] is None
    assert migrated["approval_status"] == "draft"
    assert migrated["approved_at"] is None


def test_tailored_bullet_backfill_rejects_mismatched_existing_ciphertext_without_data_loss(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_url = f"sqlite:///{tmp_path / 'mismatched-tailored-resume.db'}"
    config = migrate_to_0003(monkeypatch, database_url)
    engine = sa.create_engine(database_url)
    plaintext_bullets = [{"text": "Built FastAPI services at Acme."}]

    persisted_resume_id = seed_legacy_tailored_resume(
        engine,
        generated_bullets_json=plaintext_bullets,
    )
    ciphertext = encrypt_json(
        {"generated_bullets": [{"text": "Invented Kubernetes expertise."}]},
        purpose=f"resume:{persisted_resume_id}:generated-bullets",
    )
    _, resumes = legacy_tables()
    with engine.begin() as connection:
        connection.execute(
            sa.update(resumes)
            .where(resumes.c.id == persisted_resume_id)
            .values(generated_bullets_encrypted=ciphertext)
        )

    with pytest.raises(RuntimeError, match="plaintext and ciphertext disagree"):
        command.upgrade(config, "head")

    raw = read_raw_tailored_resume(engine)
    assert raw_json_value(raw["generated_bullets_json"]) == plaintext_bullets
    assert raw["generated_bullets_encrypted"] == ciphertext
