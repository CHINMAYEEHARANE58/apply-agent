import pytest
from pydantic import ValidationError

from app.job_sources.schemas import SourceCapability


def test_registry_entries_must_declare_supported_methods() -> None:
    with pytest.raises(ValidationError, match="discovery method"):
        SourceCapability(
            source_name="Incomplete Source",
            discovery_supported=True,
            application_supported=False,
            messaging_supported=False,
            requires_user_confirmation=True,
            authorization_verified=False,
        )
