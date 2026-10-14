"""Persist daily runs, scheduler limits and canonical discovery data."""
from alembic import op
import sqlalchemy as sa

revision = "20261014_0007"
down_revision = "20261010_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing records never declared a cadence: preserve unknown, don't guess.
    op.add_column("internship_preferences", sa.Column("compensation_period", sa.String(16), nullable=True))
    with op.batch_alter_table("user_settings") as batch:
        batch.add_column(sa.Column("timezone", sa.String(64), nullable=False, server_default="UTC"))
        batch.add_column(sa.Column("maximum_jobs_evaluated_daily", sa.Integer(), nullable=False, server_default="100"))
        batch.add_column(sa.Column("maximum_applications_prepared_daily", sa.Integer(), nullable=False, server_default="20"))
        batch.add_column(sa.Column("enabled_sources", sa.JSON(), nullable=False, server_default='["catalog"]'))
        for name, condition in [
            ("ck_settings_score", "minimum_match_score BETWEEN 0 AND 100"),
            ("ck_settings_daily_limit", "max_daily_applications BETWEEN 0 AND 50"),
            ("ck_settings_job_limit", "maximum_jobs_evaluated_daily BETWEEN 0 AND 10000"),
            ("ck_settings_prepare_limit", "maximum_applications_prepared_daily BETWEEN 0 AND 1000"),
            ("ck_settings_mode", "application_mode IN ('review', 'batch', 'authorized-auto')"),
        ]:
            batch.create_check_constraint(name, condition)
    op.add_column("jobs", sa.Column("normalized_payload", sa.JSON(), nullable=True))
    op.add_column("jobs", sa.Column("source_urls", sa.JSON(), nullable=False, server_default="[]"))
    for name in ("created_at", "updated_at"):
        op.add_column("applications", sa.Column(name, sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_table("daily_search_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("local_date", sa.Date(), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("summary", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "local_date", name="uq_daily_runs_user_date"))
    op.create_index("ix_daily_search_runs_user_id", "daily_search_runs", ["user_id"])


def downgrade() -> None:
    op.drop_column("internship_preferences", "compensation_period")
    op.drop_index("ix_daily_search_runs_user_id", table_name="daily_search_runs")
    op.drop_table("daily_search_runs")
    for name in ("updated_at", "created_at"):
        op.drop_column("applications", name)
    op.drop_column("jobs", "source_urls")
    op.drop_column("jobs", "normalized_payload")
    with op.batch_alter_table("user_settings") as batch:
        for name in ("ck_settings_score", "ck_settings_daily_limit", "ck_settings_job_limit", "ck_settings_prepare_limit", "ck_settings_mode"):
            batch.drop_constraint(name, type_="check")
        for name in ("enabled_sources", "maximum_applications_prepared_daily", "maximum_jobs_evaluated_daily", "timezone"):
            batch.drop_column(name)
