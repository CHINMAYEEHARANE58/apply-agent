"""add immutable resume versions and resume fact provenance

Revision ID: 20261004_0002
Revises: 20261004_0001
Create Date: 2026-10-04 00:30:00

The resume file itself remains in private object storage.  ``file_reference``
continues to hold only an opaque storage reference; this migration records
non-secret file integrity metadata and the immutable lineage needed to keep a
master resume reproducible after it has been used as a source of truth.
"""

from typing import Any

from alembic import op
import sqlalchemy as sa

revision = "20261004_0002"
down_revision = "20261004_0001"
branch_labels = None
depends_on = None


_RESUME_CHECK_CONSTRAINTS = (
    ("ck_resumes_version_positive", "version >= 1"),
    ("ck_resumes_source_resume_type", "source_resume_id IS NULL OR type = 'tailored'"),
    ("ck_resumes_supersedes_resume_type", "supersedes_resume_id IS NULL OR type = 'master'"),
    (
        "ck_resumes_source_of_truth_lock_type",
        "source_of_truth_locked_at IS NULL OR type = 'master'",
    ),
    ("ck_resumes_source_resume_not_self", "source_resume_id IS NULL OR source_resume_id <> id"),
    (
        "ck_resumes_supersedes_resume_not_self",
        "supersedes_resume_id IS NULL OR supersedes_resume_id <> id",
    ),
    ("ck_resumes_byte_size_limit", "byte_size IS NULL OR (byte_size > 0 AND byte_size <= 5242880)"),
    ("ck_resumes_content_sha256_length", "content_sha256 IS NULL OR length(content_sha256) = 64"),
    (
        "ck_resumes_supported_file_extension",
        "original_filename IS NULL OR lower(original_filename) LIKE '%.pdf' "
        "OR lower(original_filename) LIKE '%.docx'",
    ),
    (
        "ck_resumes_supported_content_type",
        "content_type IS NULL OR content_type IN ("
        "'application/pdf', "
        "'application/vnd.openxmlformats-officedocument.wordprocessingml.document'"
        ")",
    ),
    (
        "ck_resumes_filename_content_type_pair",
        "original_filename IS NULL OR content_type IS NULL OR "
        "(lower(original_filename) LIKE '%.pdf' AND content_type = 'application/pdf') OR "
        "(lower(original_filename) LIKE '%.docx' AND "
        "content_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')",
    ),
    (
        "ck_resumes_file_metadata_complete",
        "(original_filename IS NULL AND content_type IS NULL AND byte_size IS NULL "
        "AND content_sha256 IS NULL) OR "
        "(original_filename IS NOT NULL AND content_type IS NOT NULL AND byte_size IS NOT NULL "
        "AND content_sha256 IS NOT NULL)",
    ),
    (
        "ck_resumes_parser_status",
        "parser_status IN ('pending', 'processing', 'completed', 'failed', 'rejected')",
    ),
    (
        "ck_resumes_parser_completion_order",
        "parser_completed_at IS NULL OR parser_started_at IS NOT NULL",
    ),
    (
        "ck_resumes_approval_status",
        "approval_status IN ('draft', 'approved', 'not_applicable')",
    ),
    (
        "ck_resumes_generated_bullets_type",
        "generated_bullets_json IS NULL OR type = 'tailored'",
    ),
    (
        "ck_resumes_encrypted_generated_bullets_type",
        "generated_bullets_encrypted IS NULL OR type = 'tailored'",
    ),
    (
        "ck_resumes_encrypted_parsed_data_type",
        "parsed_resume_encrypted IS NULL OR type = 'master'",
    ),
)
_RESUME_FOREIGN_KEY_CONSTRAINTS = (
    "fk_resumes_supersedes_resume_id_resumes",
    "fk_resumes_source_resume_id_resumes",
)


def _add_resume_check_constraints(table_op: Any, *, batch: bool) -> None:
    for name, condition in _RESUME_CHECK_CONSTRAINTS:
        if batch:
            table_op.create_check_constraint(name, condition)
        else:
            table_op.create_check_constraint(name, "resumes", condition)


def _drop_resume_constraints(table_op: Any, *, batch: bool) -> None:
    for name, _ in reversed(_RESUME_CHECK_CONSTRAINTS):
        if batch:
            table_op.drop_constraint(name, type_="check")
        else:
            table_op.drop_constraint(name, "resumes", type_="check")
    for name in _RESUME_FOREIGN_KEY_CONSTRAINTS:
        if batch:
            table_op.drop_constraint(name, type_="foreignkey")
        else:
            table_op.drop_constraint(name, "resumes", type_="foreignkey")


def upgrade() -> None:
    dialect = op.get_bind().dialect.name
    # Keep versions deterministic for databases that already contain resumes.
    # New records receive version 1 by default; the application assigns the
    # next master-resume version atomically when adding a replacement.
    op.add_column(
        "resumes",
        sa.Column("version", sa.Integer(), nullable=True, server_default=sa.text("1")),
    )
    op.execute(
        """
        WITH ranked_resumes AS (
            SELECT id,
                   ROW_NUMBER() OVER (
                       PARTITION BY user_id, type
                       ORDER BY created_at, id
                   ) AS resume_version
            FROM resumes
        )
        UPDATE resumes AS resume
        SET version = (
            SELECT ranked_resumes.resume_version
            FROM ranked_resumes
            WHERE ranked_resumes.id = resume.id
        )
        """
    )
    op.add_column("resumes", sa.Column("source_resume_id", sa.Uuid(), nullable=True))
    op.add_column("resumes", sa.Column("supersedes_resume_id", sa.Uuid(), nullable=True))
    op.add_column(
        "resumes",
        sa.Column("source_of_truth_locked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("resumes", sa.Column("original_filename", sa.String(length=255), nullable=True))
    op.add_column("resumes", sa.Column("content_type", sa.String(length=128), nullable=True))
    op.add_column("resumes", sa.Column("byte_size", sa.Integer(), nullable=True))
    op.add_column("resumes", sa.Column("content_sha256", sa.String(length=64), nullable=True))
    op.add_column(
        "resumes",
        sa.Column("parser_status", sa.String(length=32), nullable=False, server_default="pending"),
    )
    op.add_column(
        "resumes",
        sa.Column("parser_started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "resumes",
        sa.Column("parser_completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("resumes", sa.Column("parser_error", sa.Text(), nullable=True))
    op.add_column(
        "resumes",
        sa.Column("approval_status", sa.String(length=32), nullable=False, server_default="draft"),
    )
    op.add_column("resumes", sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("resumes", sa.Column("generated_bullets_json", sa.JSON(), nullable=True))
    op.add_column("resumes", sa.Column("generated_bullets_encrypted", sa.Text(), nullable=True))
    op.add_column("resumes", sa.Column("parsed_resume_encrypted", sa.Text(), nullable=True))

    if dialect == "sqlite":
        with op.batch_alter_table("resumes", recreate="always") as batch_op:
            batch_op.alter_column("version", existing_type=sa.Integer(), nullable=False)
            batch_op.create_foreign_key(
                "fk_resumes_source_resume_id_resumes",
                "resumes",
                ["source_resume_id"],
                ["id"],
                ondelete="SET NULL",
            )
            batch_op.create_foreign_key(
                "fk_resumes_supersedes_resume_id_resumes",
                "resumes",
                ["supersedes_resume_id"],
                ["id"],
                ondelete="SET NULL",
            )
            _add_resume_check_constraints(batch_op, batch=True)
    else:
        op.alter_column("resumes", "version", existing_type=sa.Integer(), nullable=False)
        op.create_foreign_key(
            "fk_resumes_source_resume_id_resumes",
            "resumes",
            "resumes",
            ["source_resume_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_foreign_key(
            "fk_resumes_supersedes_resume_id_resumes",
            "resumes",
            "resumes",
            ["supersedes_resume_id"],
            ["id"],
            ondelete="SET NULL",
        )
        _add_resume_check_constraints(op, batch=False)

    op.create_index("ix_resumes_source_resume_id", "resumes", ["source_resume_id"])
    op.create_index("ix_resumes_supersedes_resume_id", "resumes", ["supersedes_resume_id"])
    op.create_index(
        "uq_resumes_user_master_version",
        "resumes",
        ["user_id", "version"],
        unique=True,
        postgresql_where=sa.text("type = 'master'"),
        sqlite_where=sa.text("type = 'master'"),
    )

    op.create_table(
        "resume_facts",
        sa.Column("fact_id", sa.Uuid(), primary_key=True),
        sa.Column(
            "resume_id",
            sa.Uuid(),
            sa.ForeignKey("resumes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("text_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.Numeric(4, 3), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "category IN ('contact', 'summary', 'education', 'experience', 'internships', "
            "'projects', 'skills', 'certifications', 'achievements', 'links', "
            "'candidate_profile')",
            name="ck_resume_facts_category",
        ),
        sa.CheckConstraint(
            "source IN ('master_resume', 'candidate_profile')",
            name="ck_resume_facts_source",
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_resume_facts_confidence",
        ),
        sa.CheckConstraint("length(trim(text)) > 0", name="ck_resume_facts_text_nonempty"),
        sa.UniqueConstraint(
            "resume_id",
            "category",
            "source",
            "text_fingerprint",
            name="uq_resume_facts_resume_category_source_text",
        ),
    )
    op.create_index("ix_resume_facts_user_id", "resume_facts", ["user_id"])
    op.create_index("ix_resume_facts_resume_id", "resume_facts", ["resume_id"])
    op.create_index("ix_resume_facts_user_category", "resume_facts", ["user_id", "category"])

    # PostgreSQL supplies a second line of defence if a future route bypasses
    # the service-level master-resume immutability check.  It intentionally
    # covers UPDATE only: explicit account/data deletion must still be able to
    # cascade through user-owned records.
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            """
            CREATE FUNCTION enforce_locked_master_resume_immutability()
            RETURNS trigger AS $$
            BEGIN
                IF OLD.type = 'master' AND OLD.source_of_truth_locked_at IS NOT NULL THEN
                    RAISE EXCEPTION 'locked master resumes are immutable';
                END IF;

                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
            """
        )
        op.execute(
            """
            CREATE TRIGGER trg_resumes_locked_master_immutable
            BEFORE UPDATE ON resumes
            FOR EACH ROW
            EXECUTE FUNCTION enforce_locked_master_resume_immutability();
            """
        )
        op.execute(
            """
            CREATE FUNCTION enforce_resume_fact_integrity()
            RETURNS trigger AS $$
            DECLARE
                parent_user_id uuid;
            BEGIN
                IF TG_OP = 'UPDATE' THEN
                    RAISE EXCEPTION 'resume facts are immutable';
                END IF;

                SELECT user_id INTO parent_user_id
                FROM resumes
                WHERE id = NEW.resume_id
                  AND type = 'master'
                  AND source_of_truth_locked_at IS NULL;

                IF parent_user_id IS NULL
                   OR parent_user_id <> NEW.user_id
                   OR NEW.source <> 'master_resume' THEN
                    RAISE EXCEPTION 'resume facts must be created with their unlocked master source';
                END IF;

                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
            """
        )
        op.execute(
            """
            CREATE TRIGGER trg_resume_facts_immutable
            BEFORE INSERT OR UPDATE ON resume_facts
            FOR EACH ROW
            EXECUTE FUNCTION enforce_resume_fact_integrity();
            """
        )


def downgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS trg_resume_facts_immutable ON resume_facts")
        op.execute("DROP FUNCTION IF EXISTS enforce_resume_fact_integrity()")
        op.execute("DROP TRIGGER IF EXISTS trg_resumes_locked_master_immutable ON resumes")
        op.execute("DROP FUNCTION IF EXISTS enforce_locked_master_resume_immutability()")

    op.drop_index("ix_resume_facts_user_category", table_name="resume_facts")
    op.drop_index("ix_resume_facts_resume_id", table_name="resume_facts")
    op.drop_index("ix_resume_facts_user_id", table_name="resume_facts")
    op.drop_table("resume_facts")

    op.drop_index("uq_resumes_user_master_version", table_name="resumes")
    op.drop_index("ix_resumes_supersedes_resume_id", table_name="resumes")
    op.drop_index("ix_resumes_source_resume_id", table_name="resumes")

    columns_to_drop = (
        "parsed_resume_encrypted",
        "generated_bullets_encrypted",
        "generated_bullets_json",
        "approved_at",
        "approval_status",
        "parser_error",
        "parser_completed_at",
        "parser_started_at",
        "parser_status",
        "content_sha256",
        "byte_size",
        "content_type",
        "original_filename",
        "source_of_truth_locked_at",
        "supersedes_resume_id",
        "source_resume_id",
        "version",
    )
    if dialect == "sqlite":
        with op.batch_alter_table("resumes", recreate="always") as batch_op:
            _drop_resume_constraints(batch_op, batch=True)
            for column in columns_to_drop:
                batch_op.drop_column(column)
    else:
        _drop_resume_constraints(op, batch=False)
        for column in columns_to_drop:
            op.drop_column("resumes", column)
