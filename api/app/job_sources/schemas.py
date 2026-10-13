from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DiscoveryMethod(StrEnum):
    API = "api"
    FEED = "feed"
    EMAIL = "email"
    MANUAL = "manual"
    AUTHORIZED_BROWSER = "authorized_browser"


class ApplicationMethod(StrEnum):
    API = "api"
    ASSISTED = "assisted"
    MANUAL = "manual"


class SourceCapability(BaseModel):
    """A required declaration for every source before it can be used."""

    model_config = ConfigDict(frozen=True)
    source_name: str = Field(min_length=1, max_length=120)
    discovery_supported: bool
    discovery_method: DiscoveryMethod
    application_supported: bool
    application_method: ApplicationMethod
    messaging_supported: bool
    requires_user_confirmation: bool
    authorization_verified: bool

    @model_validator(mode="after")
    def validate_declared_methods(self) -> "SourceCapability":
        if self.application_supported and not self.authorization_verified:
            raise ValueError("Application support requires verified authorization.")
        if self.application_method == ApplicationMethod.API and not self.application_supported:
            raise ValueError("API application method requires application support.")
        return self
