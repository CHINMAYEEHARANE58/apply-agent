"""Import all ORM models so SQLAlchemy and Alembic share one metadata registry."""

from app.applications.models import Application
from app.audit.models import AuditEvent
from app.jobs.models import Job, JobMatch, UserJob
from app.preferences.models import InternshipPreference
from app.profiles.models import CandidateProfile
from app.resumes.models import Resume, ResumeFactRecord
from app.scheduler.run_models import DailySearchRun
from app.users.models import User
from app.users.settings_models import UserSettings

__all__ = ["Application", "AuditEvent", "CandidateProfile", "DailySearchRun", "InternshipPreference", "Job", "JobMatch", "Resume", "ResumeFactRecord", "User", "UserJob", "UserSettings"]
