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
    model_provider: str = "mock"
    vision_provider: str = "mock"
    judge_provider: str = "mock"
    search_provider: str = "mock"
    embedding_provider: str = "mock"
    trefle_provider: str = "mock"
    perenual_provider: str = "mock"
    openai_api_key: str | None = None
    trefle_api_key: str | None = None
    perenual_api_key: str | None = None
    openai_text_model: str = "gpt-5.4"
    openai_vision_model: str = "gpt-5.4"
    openai_judge_model: str = "gpt-5.4"
    openai_search_model: str = "gpt-5.4"
    openai_embedding_model: str = "text-embedding-3-small"
    log_level: str = "INFO"
    tracing_enabled: bool = True
    session_cookie_name: str = "fotosintesis_session"
    session_idle_ttl_minutes: int = 30
    session_absolute_ttl_days: int = 7
    recovery_token_ttl_minutes: int = 30
    knowledge_vector_table: str = "knowledge_embeddings"
    embedding_dimension: int = 8
    trusted_source_domains: list[str] = [
        "www.rhs.org.uk",
        "gardeningsolutions.ifas.ufl.edu",
        "extension.umd.edu",
        "yardandgarden.extension.iastate.edu",
        "extension.oregonstate.edu",
        "fieldreport.caes.uga.edu",
        "hgic.clemson.edu",
        "extension.msstate.edu",
        "thespruce.com",
        "gardens.si.edu",
        "perenual.com",
        "trefle.io"
    ]


@lru_cache
def get_settings() -> Settings:
    return Settings()
