"""create internagent persistence schema

Revision ID: 20261004_0001
Revises:
Create Date: 2026-10-04 00:00:00
"""

from alembic import op
import sqlalchemy as sa

revision = "20261004_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_table(
        "jobs",
        sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("source", sa.String(100), nullable=False), sa.Column("external_job_id", sa.String(255), nullable=False), sa.Column("job_url", sa.String(2048), nullable=False), sa.Column("company", sa.String(200), nullable=False), sa.Column("title", sa.String(200), nullable=False), sa.Column("description", sa.Text(), nullable=False), sa.Column("location", sa.String(200)), sa.Column("workplace_type", sa.String(32)), sa.Column("duration", sa.String(100)), sa.Column("stipend", sa.Numeric(12, 2)), sa.Column("currency", sa.String(3)), sa.Column("skills", sa.JSON(), nullable=False), sa.Column("posted_at", sa.DateTime(timezone=True)), sa.Column("discovered_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("fingerprint", sa.String(128), nullable=False),
        sa.UniqueConstraint("source", "external_job_id", name="uq_jobs_source_external_id"), sa.UniqueConstraint("fingerprint", name="uq_jobs_fingerprint"),
    )
    op.create_index("ix_jobs_source", "jobs", ["source"]); op.create_index("ix_jobs_company", "jobs", ["company"]); op.create_index("ix_jobs_title", "jobs", ["title"])
    op.create_table("candidate_profiles", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("full_name", sa.String(200), nullable=False), sa.Column("phone", sa.String(40)), sa.Column("location", sa.String(200)), sa.Column("work_authorization", sa.String(200)), sa.Column("relocation_allowed", sa.Boolean(), nullable=False), sa.Column("linkedin_url", sa.String(2048)), sa.Column("github_url", sa.String(2048)), sa.Column("portfolio_url", sa.String(2048)), sa.UniqueConstraint("user_id", name="uq_candidate_profiles_user_id"))
    op.create_table("internship_preferences", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("roles", sa.JSON(), nullable=False), sa.Column("skills", sa.JSON(), nullable=False), sa.Column("preferred_locations", sa.JSON(), nullable=False), sa.Column("remote_allowed", sa.Boolean(), nullable=False), sa.Column("hybrid_allowed", sa.Boolean(), nullable=False), sa.Column("onsite_allowed", sa.Boolean(), nullable=False), sa.Column("min_duration", sa.Integer()), sa.Column("max_duration", sa.Integer()), sa.Column("duration_unit", sa.String(16), nullable=False), sa.Column("minimum_stipend", sa.Numeric(12, 2)), sa.Column("currency", sa.String(3)), sa.Column("allow_unpaid", sa.Boolean(), nullable=False), sa.Column("earliest_start_date", sa.Date()), sa.Column("latest_start_date", sa.Date()), sa.Column("preferred_industries", sa.JSON(), nullable=False), sa.Column("preferred_companies", sa.JSON(), nullable=False), sa.Column("excluded_companies", sa.JSON(), nullable=False), sa.Column("excluded_keywords", sa.JSON(), nullable=False), sa.Column("max_daily_applications", sa.Integer(), nullable=False), sa.Column("application_mode", sa.String(32), nullable=False), sa.UniqueConstraint("user_id", name="uq_internship_preferences_user_id"), sa.CheckConstraint("min_duration IS NULL OR max_duration IS NULL OR min_duration <= max_duration", name="ck_preferences_duration_range"), sa.CheckConstraint("max_daily_applications >= 0", name="ck_preferences_daily_limit"))
    op.create_table("resumes", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("type", sa.String(16), nullable=False), sa.Column("file_reference", sa.String(512), nullable=False), sa.Column("parsed_resume_json", sa.JSON()), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.CheckConstraint("type IN ('master', 'tailored')", name="ck_resumes_type"))
    op.create_index("ix_resumes_user_id", "resumes", ["user_id"])
    op.create_table("job_matches", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("job_id", sa.Uuid(), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False), sa.Column("score", sa.Integer(), nullable=False), sa.Column("hard_filter_passed", sa.Boolean(), nullable=False), sa.Column("matched_skills", sa.JSON(), nullable=False), sa.Column("missing_skills", sa.JSON(), nullable=False), sa.Column("explanation", sa.Text(), nullable=False), sa.UniqueConstraint("user_id", "job_id", name="uq_job_matches_user_job"), sa.CheckConstraint("score >= 0 AND score <= 100", name="ck_job_matches_score"))
    op.create_index("ix_job_matches_user_id", "job_matches", ["user_id"]); op.create_index("ix_job_matches_job_id", "job_matches", ["job_id"])
    op.create_table("applications", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("job_id", sa.Uuid(), sa.ForeignKey("jobs.id", ondelete="RESTRICT"), nullable=False), sa.Column("resume_id", sa.Uuid(), sa.ForeignKey("resumes.id", ondelete="SET NULL")), sa.Column("status", sa.String(32), nullable=False), sa.Column("cover_letter", sa.Text()), sa.Column("application_message", sa.Text()), sa.Column("submitted_at", sa.DateTime(timezone=True)), sa.Column("external_application_id", sa.String(255)), sa.UniqueConstraint("user_id", "job_id", name="uq_applications_user_job"), sa.CheckConstraint("status IN ('discovered', 'matched', 'prepared', 'awaiting_approval', 'submitted', 'assessment', 'interview', 'rejected', 'offer', 'withdrawn')", name="ck_applications_status"))
    op.create_index("ix_applications_user_id", "applications", ["user_id"]); op.create_index("ix_applications_job_id", "applications", ["job_id"])
    op.create_table("audit_events", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("event_type", sa.String(100), nullable=False), sa.Column("entity_type", sa.String(100), nullable=False), sa.Column("entity_id", sa.Uuid(), nullable=False), sa.Column("metadata", sa.JSON()), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index("ix_audit_events_user_id", "audit_events", ["user_id"]); op.create_index("ix_audit_events_event_type", "audit_events", ["event_type"])


def downgrade() -> None:
    op.drop_table("audit_events"); op.drop_table("applications"); op.drop_table("job_matches"); op.drop_table("resumes"); op.drop_table("internship_preferences"); op.drop_table("candidate_profiles"); op.drop_table("jobs"); op.drop_table("users")
