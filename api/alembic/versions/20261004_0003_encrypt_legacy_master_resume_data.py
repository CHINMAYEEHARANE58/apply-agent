"""encrypt legacy master-resume JSON before prohibiting plaintext storage.

Revision ID: 20261004_0003
Revises: 20261004_0002
Create Date: 2026-10-04 01:00:00

This is deliberately an *online* data migration.  It uses the deployment's
``APP_ENCRYPTION_KEY`` through the same authenticated-encryption primitive as
the application, so SQL-only/offline migration rendering cannot safely run it.
No key is embedded in the migration.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping

import sqlalchemy as sa

from alembic import context, op
from app.security.encryption import decrypt_json, encrypt_json

revision = "20261004_0003"
down_revision = "20261004_0002"
branch_labels = None
depends_on = None

_PLAINTEXT_MASTER_RESUME_CHECK = "ck_resumes_master_parsed_data_encrypted"


def _canonical_resume_id(value: object) -> uuid.UUID:
    """Use the same UUID string form as application-side associated data.

    SQLite may reflect UUID columns as 32-character strings while PostgreSQL
    returns ``uuid.UUID`` instances.  Normalizing before encrypting avoids an
    AAD mismatch when the application later decrypts the migrated record.
    """

    try:
        return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
    except (TypeError, ValueError) as error:
        raise RuntimeError("Legacy resume data contains an invalid resume identifier.") from error


def _encrypted_legacy_rows(bind: sa.Connection) -> list[tuple[object, str]]:
    """Validate and encrypt every plaintext row before writing any changes."""

    resumes = sa.Table("resumes", sa.MetaData(), autoload_with=bind)
    rows = bind.execute(
        sa.select(
            resumes.c.id,
            resumes.c.parsed_resume_json,
            resumes.c.parsed_resume_encrypted,
        )
        .where(
            resumes.c.type == "master",
            resumes.c.parsed_resume_json.is_not(None),
        )
        .with_for_update()
    ).mappings()

    encrypted_rows: list[tuple[object, str]] = []
    for row in rows:
        raw_json = row["parsed_resume_json"]
        if not isinstance(raw_json, Mapping):
            raise RuntimeError(
                "Legacy master resume data is malformed; migration stopped without clearing it."
            )

        resume_id = _canonical_resume_id(row["id"])
        purpose = f"resume:{resume_id}:parsed"
        existing_ciphertext = row["parsed_resume_encrypted"]
        if existing_ciphertext is not None:
            if (
                not isinstance(existing_ciphertext, str)
                or not existing_ciphertext.startswith("internagent:v1:")
            ):
                raise RuntimeError(
                    "Legacy master resume ciphertext is invalid; migration stopped without clearing data."
                )
            try:
                existing_json = decrypt_json(existing_ciphertext, purpose=purpose)
            except (RuntimeError, ValueError) as error:
                raise RuntimeError(
                    "Legacy master resume ciphertext cannot be verified; migration stopped without "
                    "clearing data."
                ) from error
            if existing_json != dict(raw_json):
                raise RuntimeError(
                    "Legacy master resume plaintext and ciphertext disagree; migration stopped "
                    "without clearing data."
                )
            encrypted_rows.append((row["id"], existing_ciphertext))
            continue

        try:
            encrypted_rows.append((row["id"], encrypt_json(dict(raw_json), purpose=purpose)))
        except (RuntimeError, TypeError, ValueError) as error:
            raise RuntimeError(
                "Legacy master resume data could not be encrypted; migration stopped without "
                "clearing data."
            ) from error

    return encrypted_rows


def _backfill_legacy_master_resume_data(bind: sa.Connection) -> None:
    """Move master resume JSON into authenticated ciphertext atomically.

    Encryption is preflighted even when no row needs conversion.  This makes a
    missing or malformed deployment key an explicit migration failure rather
    than allowing a schema that silently accepts an unusable encryption setup.
    """

    try:
        encrypt_json({}, purpose="resume:legacy-backfill-preflight:parsed")
    except (RuntimeError, TypeError, ValueError) as error:
        raise RuntimeError(
            "APP_ENCRYPTION_KEY is required to migrate legacy master resume data."
        ) from error

    encrypted_rows = _encrypted_legacy_rows(bind)
    if not encrypted_rows:
        return

    resumes = sa.Table("resumes", sa.MetaData(), autoload_with=bind)
    for resume_id, encrypted_json in encrypted_rows:
        result = bind.execute(
            sa.update(resumes)
            .where(resumes.c.id == resume_id)
            .values(
                parsed_resume_encrypted=encrypted_json,
                # A reflected SQLAlchemy JSON type serializes Python ``None``
                # as the JSON literal ``null`` by default.  Use SQL NULL so
                # the post-backfill constraint cannot retain plaintext-like
                # JSON data under a non-NULL sentinel.
                parsed_resume_json=sa.null(),
            )
        )
        if result.rowcount != 1:
            raise RuntimeError("Legacy master resume changed during encryption migration.")


def _create_no_plaintext_constraint() -> None:
    condition = "type <> 'master' OR parsed_resume_json IS NULL"
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("resumes", recreate="always") as batch_op:
            batch_op.create_check_constraint(_PLAINTEXT_MASTER_RESUME_CHECK, condition)
    else:
        op.create_check_constraint(_PLAINTEXT_MASTER_RESUME_CHECK, "resumes", condition)


def _suspend_locked_master_trigger_for_migration() -> None:
    """Temporarily remove the Phase 3 trigger under an exclusive table lock.

    The backfill changes only encrypted/legacy parsed columns, but the normal
    trigger deliberately rejects *every* update to a locked master. PostgreSQL
    migrations run transactionally, so the exclusive lock prevents concurrent
    application writes and a failure restores the original trigger on rollback.
    """

    op.execute("LOCK TABLE resumes IN ACCESS EXCLUSIVE MODE")
    op.execute("DROP TRIGGER IF EXISTS trg_resumes_locked_master_immutable ON resumes")


def _restore_locked_master_trigger_after_migration() -> None:
    op.execute(
        """
        CREATE TRIGGER trg_resumes_locked_master_immutable
        BEFORE UPDATE ON resumes
        FOR EACH ROW
        EXECUTE FUNCTION enforce_locked_master_resume_immutability();
        """
    )


def upgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError(
            "20261004_0003 encrypts private resume data and must run online with "
            "APP_ENCRYPTION_KEY configured; offline SQL output is intentionally unsupported."
        )

    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        _suspend_locked_master_trigger_for_migration()
    try:
        _backfill_legacy_master_resume_data(op.get_bind())
        _create_no_plaintext_constraint()
    finally:
        if dialect == "postgresql":
            _restore_locked_master_trigger_after_migration()


def downgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("resumes", recreate="always") as batch_op:
            batch_op.drop_constraint(_PLAINTEXT_MASTER_RESUME_CHECK, type_="check")
    else:
        op.drop_constraint(_PLAINTEXT_MASTER_RESUME_CHECK, "resumes", type_="check")
