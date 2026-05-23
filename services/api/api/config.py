from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    log_level: str = "INFO"
    version: str = "0.1.0"
    # Matches docker-compose defaults; override via DATABASE_URL env var in prod
    database_url: str = "postgresql+asyncpg://pulseuser:pulsepass@localhost:5432/pulsedb"
    redis_url: str = "redis://localhost:6379/0"
    hf_api_token: str | None = None
    hf_default_model: str = "HuggingFaceH4/zephyr-7b-beta"
    ollama_base_url: str = "http://localhost:11434"
    ollama_default_model: str = "phi3:mini"
    model_divergence_threshold: float = 0.7
    model_confidence_threshold: float = 0.4
    model_daily_paid_cap_usd: float = 2.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
