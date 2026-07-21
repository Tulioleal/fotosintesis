from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from app.schemas.common import ApiSchema


LEGACY_V1_INGESTION_POLICY_VERSION = 1
CURRENT_INGESTION_POLICY_VERSION = 1
MAX_CLAIMS_PER_PAYLOAD = 50
MAX_CLAIM_FIELD_LENGTH = 2000
MAX_ASPECT_LENGTH = 80
MAX_ASPECTS_PER_CLAIM = 20
MAX_LIMITATIONS_PER_RESULT = 10
MAX_ERROR_MESSAGE_LENGTH = 500
MAX_RESULT_DOCUMENT_IDS = 50


class JobStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    complete = "complete"
    partial = "partial"
    failed = "failed"


class JobType(str, Enum):
    ingest_validated_claims = "ingest_validated_claims"


class JobFailureCategory(str, Enum):
    invalid_payload = "invalid_payload"
    unsupported_payload_version = "unsupported_payload_version"
    unknown_job_type = "unknown_job_type"
    database_transient = "database_transient"
    provider_transient = "provider_transient"
    indexing_transient = "indexing_transient"
    invariant_violation = "invariant_violation"
    attempts_exhausted = "attempts_exhausted"
    unexpected_error = "unexpected_error"
    lease_expired = "lease_expired"
    lease_lost = "lease_lost"


class JobPayloadVersion:
    INGEST_VALIDATED_CLAIMS_V1 = 1


class SourceProvenance(str, Enum):
    trusted = "trusted"
    external_fallback = "external_fallback"


class AnswerabilityStatus(str, Enum):
    full = "full"
    partial = "partial"


class JobLimitation(str, Enum):
    some_claims_failed = "some_claims_failed"
    indexing_deferred = "indexing_deferred"


class JobError(BaseModel):
    category: JobFailureCategory
    retryable: bool = False


class ClaimedJob(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    job_type: JobType
    payload_version: int = Field(ge=1)
    payload: dict
    attempt_count: int = Field(ge=1)
    max_attempts: int = Field(ge=1)
    conversation_id: UUID | None = None
    lease_owner: str
    lease_token: str
    lease_expires_at: datetime
    available_at: datetime
    recovered: bool


class IngestValidatedClaimInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scientific_name: str = Field(min_length=1, max_length=240)
    topic: str = Field(min_length=1, max_length=120)
    source_url: HttpUrl
    source_domain: str = Field(min_length=1, max_length=180)
    source_provenance: SourceProvenance
    claim: str = Field(min_length=1, max_length=MAX_CLAIM_FIELD_LENGTH)
    evidence_quote: str = Field(min_length=1, max_length=MAX_CLAIM_FIELD_LENGTH)
    confidence: float = Field(ge=0, le=1)
    covered_aspects: list[str] = Field(min_length=1, max_length=MAX_ASPECTS_PER_CLAIM)
    required_aspects: list[str] = Field(default_factory=list, max_length=MAX_ASPECTS_PER_CLAIM)
    missing_aspects: list[str] = Field(default_factory=list, max_length=MAX_ASPECTS_PER_CLAIM)
    answerability_status: AnswerabilityStatus
    language: str = Field(default="es", max_length=10)
    source_title: str = Field(default="", max_length=240)

    @field_validator(
        "scientific_name",
        "topic",
        "source_domain",
        "claim",
        "evidence_quote",
        mode="before",
    )
    @classmethod
    def _strip_required_text(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        normalized = value.strip()
        if not normalized:
            raise ValueError("field must be non-empty after trimming whitespace")
        return normalized

    @field_validator("covered_aspects", "required_aspects", "missing_aspects")
    @classmethod
    def _validate_aspects(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        for aspect in value:
            if not isinstance(aspect, str):
                raise ValueError("aspect must be a non-empty string")
            stripped = aspect.strip()
            if not stripped:
                raise ValueError("aspect must be a non-empty string")
            if len(stripped) > MAX_ASPECT_LENGTH:
                raise ValueError(f"aspect exceeds {MAX_ASPECT_LENGTH} characters")
            normalized.append(stripped)
        return normalized


class IngestValidatedClaimsPayload(ApiSchema):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True, extra="forbid")

    payload_version: int = Field(default=JobPayloadVersion.INGEST_VALIDATED_CLAIMS_V1, ge=1)
    ingestion_policy_version: int = Field(
        default=LEGACY_V1_INGESTION_POLICY_VERSION,
        ge=1,
    )

    @field_validator("ingestion_policy_version", mode="before")
    @classmethod
    def _require_int_for_policy(cls, v: object) -> int:
        if not isinstance(v, int) or isinstance(v, bool):
            raise ValueError("ingestion_policy_version must be an integer")
        return v
    claims: list[IngestValidatedClaimInput] = Field(
        min_length=1, max_length=MAX_CLAIMS_PER_PAYLOAD
    )
    conversation_id: UUID
    answerability_status: AnswerabilityStatus

    @field_validator("payload_version")
    @classmethod
    def _validate_payload_version(cls, v: int) -> int:
        if v != JobPayloadVersion.INGEST_VALIDATED_CLAIMS_V1:
            raise ValueError(f"unsupported payload_version: {v}")
        return v


class IngestValidatedClaimsResult(BaseModel):
    succeeded: int = Field(ge=0, le=MAX_CLAIMS_PER_PAYLOAD)
    skipped: int = Field(ge=0, le=MAX_CLAIMS_PER_PAYLOAD)
    failed: int = Field(ge=0, le=MAX_CLAIMS_PER_PAYLOAD)
    limitations: list[JobLimitation] = Field(
        default_factory=list, max_length=MAX_LIMITATIONS_PER_RESULT
    )


class ReadJobResult(BaseModel):
    succeeded: int = Field(default=0, ge=0, le=MAX_CLAIMS_PER_PAYLOAD)
    skipped: int = Field(default=0, ge=0, le=MAX_CLAIMS_PER_PAYLOAD)
    failed: int = Field(default=0, ge=0, le=MAX_CLAIMS_PER_PAYLOAD)
    partial: bool = False
    limitations: list[JobLimitation] = Field(
        default_factory=list, max_length=MAX_LIMITATIONS_PER_RESULT
    )


class ReadJobError(BaseModel):
    category: JobFailureCategory
    retryable: bool = False


class JobStatusResponse(ApiSchema):
    id: UUID
    job_type: JobType
    status: JobStatus
    attempt_count: int = Field(ge=0)
    max_attempts: int = Field(ge=1)
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
    result: ReadJobResult | None = None
    last_error: ReadJobError | None = None


class EnqueueRequest(ApiSchema):
    job_type: JobType
    payload_version: int = Field(ge=1)
    payload: dict = Field(default_factory=dict)
    idempotency_key: str = Field(min_length=1, max_length=255)
    user_id: UUID | None = None
    conversation_id: UUID | None = None
    max_attempts: int = Field(default=3, ge=1)
    available_at: datetime | None = None
