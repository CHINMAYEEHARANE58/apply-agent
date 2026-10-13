import pytest
from pydantic import ValidationError

from app.job_sources.schemas import SourceCapability


def test_registry_entries_must_not_claim_unverified_application_support() -> None:
    with pytest.raises(ValidationError, match="verified authorization"):
        SourceCapability(
            source_name="Incomplete Source",
            discovery_supported=True,
            discovery_method="manual",
            application_supported=True,
            application_method="api",
            messaging_supported=False,
            requires_user_confirmation=True,
            authorization_verified=False,
        )
