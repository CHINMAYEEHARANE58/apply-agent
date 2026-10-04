"""Import all ORM models so SQLAlchemy and Alembic share one metadata registry."""

from app.applications.models import Application
from app.audit.models import AuditEvent
from app.jobs.models import Job, JobMatch
from app.preferences.models import InternshipPreference
from app.profiles.models import CandidateProfile
from app.resumes.models import Resume, ResumeFactRecord
from app.users.models import User

__all__ = ["Application", "AuditEvent", "CandidateProfile", "InternshipPreference", "Job", "JobMatch", "Resume", "ResumeFactRecord", "User"]
