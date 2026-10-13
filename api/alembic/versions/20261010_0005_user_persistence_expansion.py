"""expand persistent user profile, preference, settings, and user-job state.

Revision ID: 20261010_0005
Revises: 20261004_0004
"""

from alembic import op
import sqlalchemy as sa

revision = "20261010_0005"
down_revision = "20261004_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("password_hash", sa.String(length=512), nullable=True))
    op.add_column(
        "users", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true())
    )
    op.add_column("users", sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True))
    for name, column in (
        ("city", sa.String(120)),
        ("state", sa.String(120)),
        ("country", sa.String(120)),
        ("timezone", sa.String(64)),
        ("college", sa.String(255)),
        ("degree", sa.String(255)),
        ("graduation_year", sa.Integer()),
        ("current_role", sa.String(200)),
        ("visa_sponsorship_required", sa.Boolean()),
    ):
        op.add_column("candidate_profiles", sa.Column(name, column, nullable=True))
    for name in ("preferred_countries", "preferred_states", "preferred_cities"):
        op.add_column(
            "internship_preferences",
            sa.Column(name, sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        )
    op.add_column(
        "internship_preferences",
        sa.Column("minimum_match_score", sa.Integer(), nullable=False, server_default="75"),
    )
    op.add_column(
        "internship_preferences",
        sa.Column("search_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "internship_preferences", sa.Column("preferred_search_time", sa.String(8), nullable=True)
    )
    op.create_table(
        "user_settings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("search_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("search_time", sa.String(8)),
        sa.Column("minimum_match_score", sa.Integer(), nullable=False, server_default="75"),
        sa.Column("max_daily_applications", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("application_mode", sa.String(32), nullable=False, server_default="review"),
        sa.Column("email_notifications", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "application_notifications", sa.Boolean(), nullable=False, server_default=sa.true()
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("user_id", name="uq_user_settings_user_id"),
    )
    op.create_table(
        "user_jobs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "job_id", sa.Uuid(), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("saved", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("ignored", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("match_score", sa.Integer()),
        sa.Column("match_explanation", sa.Text()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("user_id", "job_id", name="uq_user_jobs_user_job"),
    )
    op.create_index("ix_user_jobs_user_id", "user_jobs", ["user_id"])
    op.create_index("ix_user_jobs_job_id", "user_jobs", ["job_id"])


def downgrade() -> None:
    op.drop_table("user_jobs")
    op.drop_table("user_settings")
    for name in (
        "preferred_search_time",
        "search_enabled",
        "minimum_match_score",
        "preferred_cities",
        "preferred_states",
        "preferred_countries",
    ):
        op.drop_column("internship_preferences", name)
    for name in (
        "visa_sponsorship_required",
        "current_role",
        "graduation_year",
        "degree",
        "college",
        "timezone",
        "country",
        "state",
        "city",
    ):
        op.drop_column("candidate_profiles", name)
    op.drop_column("users", "last_login_at")
    op.drop_column("users", "is_active")
    op.drop_column("users", "password_hash")
