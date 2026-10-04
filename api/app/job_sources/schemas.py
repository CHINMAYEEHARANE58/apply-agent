from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DiscoveryMethod(StrEnum):
    API = "api"
    FEED = "feed"
    MANUAL_IMPORT = "manual_import"


class ApplicationMethod(StrEnum):
    AUTHORIZED_API = "authorized_api"
    ASSISTED_MANUAL = "assisted_manual"


class SourceCapability(BaseModel):
    """A required declaration for every source before it can be used."""

    model_config = ConfigDict(frozen=True)
    source_name: str = Field(min_length=1, max_length=120)
    discovery_supported: bool
    discovery_method: DiscoveryMethod | None = None
    application_supported: bool
    application_method: ApplicationMethod | None = None
    messaging_supported: bool
    requires_user_confirmation: bool
    authorization_verified: bool

    @model_validator(mode="after")
    def validate_declared_methods(self) -> "SourceCapability":
        if self.discovery_supported and self.discovery_method is None:
            raise ValueError("Discovery-supported sources must declare a discovery method.")
        if self.application_supported and self.application_method is None:
            raise ValueError("Application-supported sources must declare an application method.")
        return self
