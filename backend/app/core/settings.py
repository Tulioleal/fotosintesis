import json
from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.limiter.policy import (
    EndpointCategory,
    EndpointPolicy,
    LimitProfile,
    LimiterPolicy,
    StorageFailureMode,
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    app_name: str = "Fotosintesis AI API"
    environment: str = Field(default="local", validation_alias="APP_ENV")
    cors_origins: list[str] = ["http://localhost:3000"]
    database_url: str = "postgresql+asyncpg://fotosintesis:fotosintesis@localhost:5432/fotosintesis"
    object_storage_bucket: str = "fotosintesis-local"
    object_storage_provider: str = Field(default="local", validation_alias="OBJECT_STORAGE_PROVIDER")
    object_storage_local_root: str = Field(
        default="/tmp/storage-data", validation_alias="OBJECT_STORAGE_LOCAL_ROOT"
    )
    object_storage_access_key: str | None = Field(default=None, validation_alias="OBJECT_STORAGE_ACCESS_KEY")
    object_storage_secret_key: str | None = Field(default=None, validation_alias="OBJECT_STORAGE_SECRET_KEY")
    object_storage_endpoint: str | None = Field(default=None, validation_alias="OBJECT_STORAGE_ENDPOINT")
    gcp_project_id: str | None = Field(default=None, validation_alias="GCP_PROJECT_ID")
    model_provider: str = "mock"
    vision_provider: str = "mock"
    judge_provider: str = "mock"
    search_provider: str = "mock"
    embedding_provider: str = "mock"
    trefle_provider: str = "mock"
    perenual_provider: str = "mock"
    model_providers: list[str] | None = None
    judge_providers: list[str] | None = None
    search_providers: list[str] | None = None
    vision_providers: list[str] | None = None
    openai_api_key: str | None = None
    gemini_api_key: str | None = None
    trefle_api_key: str | None = None
    perenual_api_key: str | None = None
    gbif_base_url: str = Field(
        default="https://api.gbif.org/v1/species/match",
        validation_alias="GBIF_BASE_URL",
    )
    openai_text_model: str = "gpt-5.4"
    openai_classifier_model: str = "gpt-5.4-mini"
    openai_vision_model: str = "gpt-5.4"
    openai_judge_model: str = "gpt-5.4"
    openai_search_model: str = "gpt-5.4"
    openai_embedding_model: str = "text-embedding-3-small"
    gemini_text_model: str = "gemini-2.5-flash"
    gemini_classifier_model: str = "gemini-2.5-flash-lite"
    gemini_vision_model: str = "gemini-2.5-flash"
    gemini_judge_model: str = "gemini-2.5-flash"
    gemini_search_model: str = "gemini-2.5-flash"
    log_level: str = "INFO"
    session_cookie_name: str = "fotosintesis_session"
    session_idle_ttl_minutes: int = 30
    session_absolute_ttl_days: int = 7
    recovery_token_ttl_minutes: int = 30
    knowledge_vector_table: str = "knowledge_embeddings"
    embedding_dimension: int = 8
    assistant_classifier_timeout_seconds: float = 8.0
    assistant_evidence_validation_threshold: float = 0.75
    assistant_safety_validation_threshold: float = 0.85
    assistant_strong_answer_validation_threshold: float = 0.30
    assistant_judge_timeout_seconds: float = 25.0
    assistant_web_search_timeout_seconds: float = 20.0
    model_provider_attempt_timeout_seconds: float = 30.0
    judge_provider_attempt_timeout_seconds: float = 30.0
    search_provider_attempt_timeout_seconds: float = 25.0
    vision_provider_attempt_timeout_seconds: float = 30.0
    model_circuit_breaker_duration_seconds: float = 60.0
    judge_circuit_breaker_duration_seconds: float = 60.0
    search_circuit_breaker_duration_seconds: float = 60.0
    vision_circuit_breaker_duration_seconds: float = 60.0
    jobs_producer_enabled: bool = Field(default=False, validation_alias="JOBS_PRODUCER_ENABLED")
    jobs_worker_enabled: bool = Field(default=False, validation_alias="JOBS_WORKER_ENABLED")
    jobs_poll_interval_seconds: float = Field(default=5.0, gt=0, validation_alias="JOBS_POLL_INTERVAL_SECONDS")
    jobs_batch_size: int = Field(default=10, gt=0, validation_alias="JOBS_BATCH_SIZE")
    jobs_worker_concurrency: int = Field(default=5, gt=0, validation_alias="JOBS_WORKER_CONCURRENCY")
    jobs_lease_duration_seconds: float = Field(default=300.0, gt=0, validation_alias="JOBS_LEASE_DURATION_SECONDS")
    jobs_lease_renewal_interval_seconds: float = Field(default=60.0, gt=0, validation_alias="JOBS_LEASE_RENEWAL_INTERVAL_SECONDS")
    jobs_max_attempts_default: int = Field(default=3, ge=1, validation_alias="JOBS_MAX_ATTEMPTS_DEFAULT")
    jobs_backoff_base_seconds: float = Field(default=10.0, gt=0, validation_alias="JOBS_BACKOFF_BASE_SECONDS")
    jobs_backoff_cap_seconds: float = Field(default=3600.0, gt=0, validation_alias="JOBS_BACKOFF_CAP_SECONDS")
    jobs_shutdown_drain_seconds: float = Field(default=30.0, gt=0, validation_alias="JOBS_SHUTDOWN_DRAIN_SECONDS")
    jobs_metrics_host: str = Field(default="0.0.0.0", validation_alias="JOBS_METRICS_HOST")
    jobs_metrics_port: int = Field(default=9100, ge=0, lt=65536, validation_alias="JOBS_METRICS_PORT")
    jobs_required_contracts: str = Field(
        default="",
        validation_alias="JOBS_REQUIRED_CONTRACTS",
    )

    auth_limiter_enabled: bool = Field(default=False, validation_alias="AUTH_LIMITER_ENABLED")
    auth_limiter_hmac_secret: str | None = Field(
        default=None, validation_alias="AUTH_LIMITER_HMAC_SECRET"
    )
    auth_limiter_hmac_key_version: int = Field(
        default=1, ge=1, validation_alias="AUTH_LIMITER_HMAC_KEY_VERSION"
    )
    auth_limiter_assertion_secret: str | None = Field(
        default=None, validation_alias="AUTH_LIMITER_ASSERTION_SECRET"
    )
    auth_limiter_max_retry_after_seconds: int = Field(
        default=3600, ge=1, validation_alias="AUTH_LIMITER_MAX_RETRY_AFTER_SECONDS"
    )
    auth_limiter_retention_seconds: int = Field(
        default=86400, gt=0, validation_alias="AUTH_LIMITER_RETENTION_SECONDS"
    )
    auth_limiter_cleanup_batch_size: int = Field(
        default=1000, gt=0, validation_alias="AUTH_LIMITER_CLEANUP_BATCH_SIZE"
    )
    auth_limiter_profiles: str = Field(
        default="",
        validation_alias="AUTH_LIMITER_PROFILES",
        description=(
            "JSON mapping of endpoint category to {source, account, storage_failure_mode} "
            "limit profiles; e.g. "
            '{"registration":{"source":{"limit":10,"window_seconds":3600},'
            '"account":null,"storage_failure_mode":"fail_closed"}}'
        ),
    )

    @model_validator(mode="after")
    def _validate_job_settings(self) -> "Settings":
        if self.jobs_lease_renewal_interval_seconds >= self.jobs_lease_duration_seconds:
            raise ValueError(
                "jobs_lease_renewal_interval_seconds must be less than jobs_lease_duration_seconds"
            )
        return self

    def limiter_policy(self) -> LimiterPolicy:
        """Build the validated limiter policy from configured profiles.

        When enforcement is disabled, an empty but structurally complete
        policy is returned so callers can gate on ``auth_limiter_enabled``
        without special-casing construction. When enforcement is enabled, the
        policy must cover every closed endpoint category and use safe
        production values, otherwise a ``ValueError`` is raised.
        """
        parsed: dict[str, object] = {}
        if self.auth_limiter_profiles:
            try:
                parsed = json.loads(self.auth_limiter_profiles)
            except json.JSONDecodeError as error:
                raise ValueError("auth_limiter_profiles is not valid JSON") from error

        # The distributed authentication boundary is mandatory in production: a
        # missing or incorrect setting must fail startup rather than silently
        # removing the whole abuse boundary. Disabled mode stays available only
        # outside production (local, test, dev).
        if self.environment in {"prod", "production"} and not self.auth_limiter_enabled:
            raise ValueError(
                "auth_limiter_enabled must be true when APP_ENV is prod or production"
            )

        endpoints: dict[EndpointCategory, EndpointPolicy] = {}
        for raw_category, raw_policy in parsed.items():
            if raw_category not in EndpointCategory.__members__:
                raise ValueError(f"unknown auth limiter endpoint category: {raw_category}")
            category = EndpointCategory[raw_category]
            if not isinstance(raw_policy, dict):
                raise ValueError(f"auth limiter policy for {raw_category} must be an object")
            source = raw_policy.get("source")
            if not isinstance(source, dict):
                raise ValueError(f"auth limiter policy for {raw_category} requires a source rule")
            account = raw_policy.get("account")
            failure_mode = raw_policy.get("storage_failure_mode", "fail_closed")
            if failure_mode not in StorageFailureMode.__members__:
                raise ValueError(
                    f"unknown storage_failure_mode for {raw_category}: {failure_mode!r}"
                )
            endpoints[category] = EndpointPolicy(
                source=LimitProfile.model_validate(source),
                account=LimitProfile.model_validate(account) if account else None,
                storage_failure_mode=StorageFailureMode[failure_mode],
            )

        if self.auth_limiter_enabled:
            if not self.auth_limiter_hmac_secret:
                raise ValueError("auth_limiter_hmac_secret is required when auth_limiter_enabled")
            if not self.auth_limiter_assertion_secret:
                raise ValueError(
                    "auth_limiter_assertion_secret is required when auth_limiter_enabled"
                )
            # Account-aware categories must reject unsafe source-only profiles
            # when enforcement is enabled. Registration and authjs_post may
            # legitimately stay source-only. A fully absent category is handled
            # by the policy's coverage validation below.
            account_sensitive = {
                EndpointCategory.credential_verification,
                EndpointCategory.recovery_initiation,
                EndpointCategory.recovery_confirmation,
            }
            missing_account = [
                category.value
                for category in account_sensitive
                if category in endpoints and endpoints[category].account is None
            ]
            if missing_account:
                raise ValueError(
                    "account profile required when auth_limiter_enabled for: "
                    + ", ".join(sorted(missing_account))
                )
            return LimiterPolicy(
                endpoints=endpoints,
                max_retry_after_seconds=self.auth_limiter_max_retry_after_seconds,
                retention_seconds=self.auth_limiter_retention_seconds,
                hmac_key_version=self.auth_limiter_hmac_key_version,
            )
        return LimiterPolicy(
            endpoints={
                category: EndpointPolicy(
                    source=LimitProfile(limit=1, window_seconds=3600),
                    account=LimitProfile(limit=1, window_seconds=3600)
                    if category in (EndpointCategory.credential_verification, EndpointCategory.recovery_initiation, EndpointCategory.recovery_confirmation)
                    else None,
                )
                for category in EndpointCategory
            },
            max_retry_after_seconds=self.auth_limiter_max_retry_after_seconds,
            retention_seconds=self.auth_limiter_retention_seconds,
            hmac_key_version=self.auth_limiter_hmac_key_version,
        )

    trusted_source_domains: list[str] = [
        "rhs.org.uk",
        "gardeningsolutions.ifas.ufl.edu",
        "yardandgarden.extension.iastate.edu",
        "extension.oregonstate.edu",
        "fieldreport.caes.uga.edu",
        "hgic.clemson.edu",
        "extension.msstate.edu",
        "extension.umn.edu",
        "extension.psu.edu",
        "extension.unh.edu",
        "extension.wvu.edu",
        "hort.extension.wisc.edu",
        "extension.missouri.edu",
        "extension.illinois.edu",
        "plants.ces.ncsu.edu",
        "missouribotanicalgarden.org",
        "thespruce.com",
        "gardens.si.edu",
        "ccenassau.org",
        "garden.org",
        "ourhouseplants.com",
        "perenual.com",
        "trefle.io"
    ]


@lru_cache
def get_settings() -> Settings:
    return Settings()
