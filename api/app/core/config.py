from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "InternAgent API"
    api_v1_prefix: str = "/api/v1"
    database_url: str = "postgresql+psycopg://internagent:local@localhost:5432/internagent"
    redis_url: str = "redis://localhost:6379/0"
    app_encryption_key: str = "development-only-not-a-secret"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
