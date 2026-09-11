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
    tpm_limit: int = 100_000
    default_completion_estimate: int = 512
    provider_max_retries: int = 3
    provider_failure_threshold: int = 5
    provider_recovery_timeout: float = 30.0
    backup_openai_base_url: str | None = None
    backup_openai_api_key: str | None = None
    enable_hedging: bool = False
    hedge_delay_s: float = 0.15


@lru_cache
def get_settings() -> Settings:
    return Settings()