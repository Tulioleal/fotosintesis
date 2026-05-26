from functools import lru_cache

from pydantic import AnyUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Fotosintesis AI API"
    environment: str = Field(default="local", validation_alias="APP_ENV")
    api_prefix: str = "/api"
    cors_origins: list[str] = ["http://localhost:3000"]
    database_url: str = "postgresql+asyncpg://fotosintesis:fotosintesis@localhost:5432/fotosintesis"
    object_storage_endpoint: AnyUrl | None = None
    object_storage_bucket: str = "fotosintesis-local"
    object_storage_access_key: str | None = None
    object_storage_secret_key: str | None = None
    provider_profile: str = "mock"
    log_level: str = "INFO"
    tracing_enabled: bool = True
    session_cookie_name: str = "fotosintesis_session"
    session_idle_ttl_minutes: int = 30
    session_absolute_ttl_days: int = 7
    recovery_token_ttl_minutes: int = 30
    knowledge_vector_table: str = "knowledge_embeddings"
    embedding_dimension: int = 8
    trusted_source_domains: list[str] = [
        "gbif.org",
        "powo.science.kew.org",
        "worldfloraonline.org",
        "tropicos.org",
        "eol.org",
        "example.org",
    ]


@lru_cache
def get_settings() -> Settings:
    return Settings()
