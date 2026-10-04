"""encrypt legacy tailored-resume bullets before prohibiting plaintext storage.

Revision ID: 20261004_0004
Revises: 20261004_0003
Create Date: 2026-10-04 01:15:00

Like the preceding master-resume backfill, this migration must run online.
It deliberately uses the deployment encryption key through the application
primitive rather than embedding or rendering secret-dependent ciphertext in
SQL.
"""

from __future__ import annotations

import uuid
from typing import Any

import sqlalchemy as sa
from pydantic import ValidationError

from alembic import context, op
from app.resumes.facts import GeneratedResumeBullet
from app.security.encryption import decrypt_json, encrypt_json

revision = "20261004_0004"
down_revision = "20261004_0003"
branch_labels = None
depends_on = None

_NO_PLAINTEXT_TAILORED_BULLETS_CHECK = "ck_resumes_tailored_bullets_encrypted"


def _canonical_resume_id(value: object) -> uuid.UUID:
    """Normalize reflected UUID values for stable authenticated data."""

    try:
        return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
    except (TypeError, ValueError) as error:
        raise RuntimeError("Legacy tailored resume contains an invalid resume identifier.") from error


def _canonical_bullets(value: object) -> list[dict[str, Any]]:
    """Validate the persisted legacy payload before moving or clearing it.

    A malformed legacy row is an integrity event, not an excuse to discard
    candidate material.  The migration stops before any row is updated so an
    operator can resolve it without data loss.
    """

    if not isinstance(value, list):
        raise RuntimeError(
            "Legacy tailored resume bullets are malformed; migration stopped without clearing them."
        )
    try:
        return [GeneratedResumeBullet.model_validate(item).model_dump(mode="json") for item in value]
    except (TypeError, ValidationError) as error:
        raise RuntimeError(
            "Legacy tailored resume bullets are malformed; migration stopped without clearing them."
        ) from error


def _validated_ciphertext(
    value: object,
    *,
    purpose: str,
    expected_bullets: list[dict[str, Any]],
) -> str:
    if not isinstance(value, str) or not value.startswith("internagent:v1:"):
        raise RuntimeError(
            "Legacy tailored resume ciphertext is invalid; migration stopped without clearing data."
        )
    try:
        encrypted_payload = decrypt_json(value, purpose=purpose)
        encrypted_bullets = _canonical_bullets(encrypted_payload.get("generated_bullets"))
    except (RuntimeError, TypeError, ValueError) as error:
        raise RuntimeError(
            "Legacy tailored resume ciphertext cannot be verified; migration stopped without clearing data."
        ) from error
    if encrypted_bullets != expected_bullets:
        raise RuntimeError(
            "Legacy tailored resume plaintext and ciphertext disagree; migration stopped without "
            "clearing data."
        )
    return value


def _encrypted_legacy_rows(
    bind: sa.Connection,
) -> tuple[list[tuple[object, str]], list[object]]:
    """Preflight every conversion before clearing plaintext from any row.

    SQLAlchemy's JSON type historically bound ``None`` as the JSON literal
    ``null``. It is not candidate content, but it is not SQL NULL either, so
    collect those rows for normalization before adding the SQL-NULL check.
    """

    resumes = sa.Table("resumes", sa.MetaData(), autoload_with=bind)
    rows = bind.execute(
        sa.select(
            resumes.c.id,
            resumes.c.generated_bullets_json,
            resumes.c.generated_bullets_encrypted,
        )
        .where(
            resumes.c.type == "tailored",
            resumes.c.generated_bullets_json.is_not(None),
        )
        .with_for_update()
    ).mappings()

    encrypted_rows: list[tuple[object, str]] = []
    json_null_rows: list[object] = []
    for row in rows:
        resume_id = _canonical_resume_id(row["id"])
        purpose = f"resume:{resume_id}:generated-bullets"
        raw_bullets = row["generated_bullets_json"]
        if raw_bullets is None:
            json_null_rows.append(row["id"])
            continue
        expected_bullets = _canonical_bullets(raw_bullets)
        existing_ciphertext = row["generated_bullets_encrypted"]

        if existing_ciphertext is not None:
            ciphertext = _validated_ciphertext(
                existing_ciphertext,
                purpose=purpose,
                expected_bullets=expected_bullets,
            )
        else:
            try:
                ciphertext = encrypt_json(
                    {"generated_bullets": expected_bullets},
                    purpose=purpose,
                )
            except (RuntimeError, TypeError, ValueError) as error:
                raise RuntimeError(
                    "Legacy tailored resume bullets could not be encrypted; migration stopped without "
                    "clearing data."
                ) from error
            # Authenticated encryption and serialization must both be verified
            # before the raw candidate content becomes eligible for removal.
            _validated_ciphertext(
                ciphertext,
                purpose=purpose,
                expected_bullets=expected_bullets,
            )
        encrypted_rows.append((row["id"], ciphertext))

    return encrypted_rows, json_null_rows


def _backfill_legacy_tailored_bullets(bind: sa.Connection) -> None:
    """Atomically convert legacy bullets to authenticated ciphertext."""

    try:
        encrypt_json(
            {"generated_bullets": []},
            purpose="resume:legacy-backfill-preflight:generated-bullets",
        )
    except (RuntimeError, TypeError, ValueError) as error:
        raise RuntimeError(
            "APP_ENCRYPTION_KEY is required to migrate legacy tailored resume bullets."
        ) from error

    encrypted_rows, json_null_rows = _encrypted_legacy_rows(bind)
    if not encrypted_rows and not json_null_rows:
        return

    resumes = sa.Table("resumes", sa.MetaData(), autoload_with=bind)
    for resume_id, ciphertext in encrypted_rows:
        result = bind.execute(
            sa.update(resumes)
            .where(resumes.c.id == resume_id)
            .values(
                generated_bullets_encrypted=ciphertext,
                # Reflected JSON columns can serialize Python ``None`` as the
                # JSON literal ``null``. Use SQL NULL so the new check
                # constraint conclusively excludes plaintext payloads.
                generated_bullets_json=sa.null(),
            )
        )
        if result.rowcount != 1:
            raise RuntimeError("Legacy tailored resume changed during encryption migration.")

    for resume_id in json_null_rows:
        result = bind.execute(
            sa.update(resumes)
            .where(resumes.c.id == resume_id)
            .values(generated_bullets_json=sa.null())
        )
        if result.rowcount != 1:
            raise RuntimeError("Legacy tailored resume changed during encryption migration.")


def _reset_legacy_tailored_approvals(bind: sa.Connection) -> None:
    """Require current fact verification for every previously approved draft.

    Older approvals may predate the evidence-bound verifier.  Keeping them
    approved would permit use of an unverified generated resume even when the
    content itself did not require a plaintext-to-ciphertext conversion.
    """

    resumes = sa.Table("resumes", sa.MetaData(), autoload_with=bind)
    bind.execute(
        sa.update(resumes)
        .where(
            resumes.c.type == "tailored",
            resumes.c.approval_status == "approved",
        )
        .values(
            approval_status="draft",
            approved_at=sa.null(),
        )
    )


def _create_no_plaintext_constraint() -> None:
    condition = "type <> 'tailored' OR generated_bullets_json IS NULL"
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("resumes", recreate="always") as batch_op:
            batch_op.create_check_constraint(_NO_PLAINTEXT_TAILORED_BULLETS_CHECK, condition)
    else:
        op.create_check_constraint(_NO_PLAINTEXT_TAILORED_BULLETS_CHECK, "resumes", condition)


def _lock_for_approval_reset() -> None:
    """Prevent concurrent tailored approval writes during the migration."""

    if op.get_bind().dialect.name == "postgresql":
        op.execute("LOCK TABLE resumes IN SHARE ROW EXCLUSIVE MODE")


def upgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError(
            "20261004_0004 encrypts private tailored resume data and must run online with "
            "APP_ENCRYPTION_KEY configured; offline SQL output is intentionally unsupported."
        )

    _lock_for_approval_reset()
    _backfill_legacy_tailored_bullets(op.get_bind())
    _reset_legacy_tailored_approvals(op.get_bind())
    _create_no_plaintext_constraint()


def downgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("resumes", recreate="always") as batch_op:
            batch_op.drop_constraint(_NO_PLAINTEXT_TAILORED_BULLETS_CHECK, type_="check")
    else:
        op.drop_constraint(_NO_PLAINTEXT_TAILORED_BULLETS_CHECK, "resumes", type_="check")
