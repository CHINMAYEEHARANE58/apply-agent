from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "InternAgent API"
    api_v1_prefix: str = "/api/v1"
    # Fail closed: the development identity header is never enabled merely
    # because a deployment omitted an environment setting.
    app_environment: str = "production"
    database_url: str = "postgresql+psycopg://internagent:local@localhost:5432/internagent"
    redis_url: str = "redis://localhost:6379/0"
    # Deliberately has no source-code fallback: private resume storage refuses
    # to write until an environment-provided secret is configured.
    app_encryption_key: str = ""
    private_resume_storage_path: str = "/tmp/internagent-private-resumes"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
