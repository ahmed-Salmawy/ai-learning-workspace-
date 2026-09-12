from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ALW_", env_file=".env", extra="ignore")

    app_name: str = "ai-learning-workspace"
    environment: str = "dev"
    log_level: str = "INFO"

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/postgres"
    db_echo: bool = False

    openai_base_url: str | None = None
    openai_api_key: SecretStr | None = None
    llm_model: str | None = None
    embedding_model: str | None = None
    embedding_dimension: int = 1536

    storage_root: str = "var/storage"
    cors_origins: str = "http://localhost:3000"


@lru_cache
def get_settings() -> Settings:
    return Settings()
