from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SB_", env_file=".env", extra="ignore")

    env: str = "local"
    log_level: str = "INFO"
    database_url: str = "postgresql+asyncpg://switchboard:switchboard@localhost:5432/switchboard"
    db_pool_size: int = 10
    db_max_overflow: int = 5
    redis_url: str = "redis://localhost:6379/0"
    readiness_timeout_s: float = 2.0
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    provider_timeout_s: float = 20.0
    rpm_limit: int = 60


@lru_cache
def get_settings() -> Settings:
    return Settings()