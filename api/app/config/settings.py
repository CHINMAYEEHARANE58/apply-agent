from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "InternAgent API"
    api_v1_prefix: str = "/api/v1"
    # Fail closed: the development identity header is never enabled merely
    # because a deployment omitted an environment setting.
    app_environment: str = "production"
    database_url: str = "postgresql+psycopg://internagent:local@localhost:5432/internagent"
    # Neon pooled URL for requests, unpooled URL for Alembic.
    database_direct_url: str = ""
    auth_provider: str = "clerk"
    clerk_issuer: str = ""
    clerk_jwt_key: str = ""
    clerk_secret_key: str = ""
    clerk_authorized_parties: list[str] = []
    redis_url: str = "redis://localhost:6379/0"
    # Deliberately has no source-code fallback: private resume storage refuses
    # to write until an environment-provided secret is configured.
    app_encryption_key: str = ""
    private_resume_storage_path: str = "/tmp/internagent-private-resumes"
    allowed_origins: list[str] = []
    require_https: bool = True
    rate_limit_per_minute: int = 120
    secret_manager_provider: str = "environment"

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    model_config = SettingsConfigDict(env_file=(str(Path(__file__).resolve().parents[3] / ".env"), ".env"), extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
