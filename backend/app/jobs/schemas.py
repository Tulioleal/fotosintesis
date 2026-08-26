from __future__ import annotations

import base64
import binascii
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Literal, Self, TypeAlias
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator

from app.schemas.common import ApiSchema


LEGACY_V1_INGESTION_POLICY_VERSION = 1
CURRENT_INGESTION_POLICY_VERSION = 2
MAX_CLAIMS_PER_PAYLOAD = 50
MAX_CLAIM_FIELD_LENGTH = 2000
MAX_ASPECT_LENGTH = 80
MAX_ASPECTS_PER_CLAIM = 20
MAX_LIMITATIONS_PER_RESULT = 10
MAX_ERROR_MESSAGE_LENGTH = 500
MAX_RESULT_DOCUMENT_IDS = 50
MAX_ENRICHMENT_ASPECTS = 32


class JobStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    complete = "complete"
    partial = "partial"
    failed = "failed"


class JobType(str, Enum):
    ingest_validated_claims = "ingest_validated_claims"
    enrich_confirmed_plant = "enrich_confirmed_plant"
    refresh_profile = "refresh_profile"


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
    insufficient_evidence = "insufficient_evidence"


class JobPayloadVersion:
    INGEST_VALIDATED_CLAIMS_V1 = 1
    ENRICH_CONFIRMED_PLANT_V1 = 1
    REFRESH_PROFILE_V1 = 1


class SourceProvenance(str, Enum):
    trusted = "trusted"
    external_fallback = "external_fallback"


class AnswerabilityStatus(str, Enum):
    full = "full"
    partial = "partial"


class JobLimitation(str, Enum):
    some_claims_failed = "some_claims_failed"
    indexing_deferred = "indexing_deferred"


class EnrichmentLimitation(str, Enum):
    missing_required_aspects = "missing_required_aspects"
    safety_evidence_rejected = "safety_evidence_rejected"
    retry_exhausted = "retry_exhausted"
    workflow_incomplete = "workflow_incomplete"
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
    created_at: datetime
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


class CanonicalSpeciesIdentityFields(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    accepted_gbif_key: int | None = Field(default=None, gt=0)
    normalized_binomial: str = Field(min_length=3, max_length=240)

    @field_validator("accepted_gbif_key", mode="before")
    @classmethod
    def _reject_boolean_key(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("accepted_gbif_key must be a positive integer")
        return value

    @field_validator("normalized_binomial")
    @classmethod
    def _normalize_binomial(cls, value: str) -> str:
        from app.enrichment.identity import CanonicalSpeciesIdentity

        identity = CanonicalSpeciesIdentity(
            accepted_gbif_key=None,
            normalized_binomial=value,
            taxonomy_validated=True,
        )
        assert identity.normalized_binomial is not None
        return identity.normalized_binomial


class EnrichConfirmedPlantPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    payload_version: Literal[1] = JobPayloadVersion.ENRICH_CONFIRMED_PLANT_V1
    policy_version: int = Field(ge=1)
    species: CanonicalSpeciesIdentityFields
    taxonomy_provenance_id: UUID
    run_id: UUID


class EnrichmentJobResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outcome: Literal["complete", "partial"]
    policy_version: int = Field(ge=1)
    covered_aspects: list[str] = Field(max_length=MAX_ENRICHMENT_ASPECTS)
    missing_aspects: list[str] = Field(max_length=MAX_ENRICHMENT_ASPECTS)
    covered_count: int = Field(ge=0, le=MAX_ENRICHMENT_ASPECTS)
    missing_count: int = Field(ge=0, le=MAX_ENRICHMENT_ASPECTS)
    limitations: list[EnrichmentLimitation] = Field(
        default_factory=list,
        max_length=MAX_LIMITATIONS_PER_RESULT,
    )
    acquisition_avoided: bool = False

    @field_validator("covered_aspects", "missing_aspects")
    @classmethod
    def _bounded_unique_aspects(cls, value: list[str]) -> list[str]:
        normalized = [str(item).strip() for item in value]
        if any(not item or len(item) > MAX_ASPECT_LENGTH for item in normalized):
            raise ValueError("result aspects must be bounded non-empty identifiers")
        if len(set(normalized)) != len(normalized):
            raise ValueError("result aspects must be unique")
        return normalized

    @model_validator(mode="after")
    def _validate_aggregate(self) -> "EnrichmentJobResult":
        covered = set(self.covered_aspects)
        missing = set(self.missing_aspects)
        if covered & missing:
            raise ValueError("covered and missing aspects must be disjoint")
        if self.covered_count != len(self.covered_aspects):
            raise ValueError("covered_count must match covered_aspects")
        if self.missing_count != len(self.missing_aspects):
            raise ValueError("missing_count must match missing_aspects")
        if not self.covered_aspects:
            raise ValueError("terminal enrichment results require useful coverage")
        from app.enrichment.policy import get_enrichment_policy

        policy = get_enrichment_policy(self.policy_version)
        required = {aspect.value for aspect in policy.required_aspects}
        if covered | missing != required:
            raise ValueError("result aspects must exactly partition the selected policy")
        if self.outcome == "complete" and (self.missing_aspects or self.limitations):
            raise ValueError("complete enrichment cannot have missing aspects or limitations")
        if self.outcome == "complete" and covered != required:
            raise ValueError("complete enrichment requires all aspects covered")
        if self.outcome == "partial":
            if self.missing_aspects:
                if EnrichmentLimitation.missing_required_aspects not in self.limitations:
                    raise ValueError(
                        "semantic partial requires the missing-required-aspects limitation"
                    )
            else:
                operational = any(
                    limitation in self.limitations
                    for limitation in (
                        EnrichmentLimitation.retry_exhausted,
                        EnrichmentLimitation.workflow_incomplete,
                        EnrichmentLimitation.indexing_deferred,
                    )
                )
                if not operational:
                    raise ValueError(
                        "partial without missing aspects requires an operational limitation"
                    )
        return self


class RefreshProfilePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    payload_version: Literal[1] = JobPayloadVersion.REFRESH_PROFILE_V1
    policy_version: int = Field(ge=1)
    species: CanonicalSpeciesIdentityFields
    changed_aspects: list[str] = Field(
        default_factory=list, max_length=MAX_ENRICHMENT_ASPECTS
    )
    fingerprint: str = Field(min_length=1, max_length=64)
    run_id: UUID


class ProfileRefreshJobResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outcome: Literal["complete", "partial", "noop"]
    policy_version: int = Field(ge=1)
    regenerated_sections: list[str] = Field(
        default_factory=list, max_length=MAX_ENRICHMENT_ASPECTS
    )
    stale_sections: list[str] = Field(
        default_factory=list, max_length=MAX_ENRICHMENT_ASPECTS
    )
    limitations: list[EnrichmentLimitation] = Field(
        default_factory=list,
        max_length=MAX_LIMITATIONS_PER_RESULT,
    )


class ReadJobResult(BaseModel):
    succeeded: int = Field(default=0, ge=0, le=MAX_CLAIMS_PER_PAYLOAD)
    skipped: int = Field(default=0, ge=0, le=MAX_CLAIMS_PER_PAYLOAD)
    failed: int = Field(default=0, ge=0, le=MAX_CLAIMS_PER_PAYLOAD)
    partial: bool = False
    limitations: list[JobLimitation] = Field(
        default_factory=list, max_length=MAX_LIMITATIONS_PER_RESULT
    )


JobResult: TypeAlias = (
    ReadJobResult
    | EnrichmentJobResult
    | ProfileRefreshJobResult
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
    result: JobResult | None = None
    last_error: ReadJobError | None = None


class CandidateEnrichmentStatus(ApiSchema):
    candidate_id: UUID
    policy_version: int = Field(ge=1)
    job: JobStatusResponse


class EnrichmentActivityPhase(str, Enum):
    evidence = "evidence"
    profile_refresh = "profile_refresh"


class EnrichmentActivityResult(BaseModel):
    """Bounded, metadata-only outcome for the cross-page activity view.

    Counts and limitation categories only: never raw aspects, source bodies,
    claims, quotes, or provider diagnostics.
    """

    model_config = ConfigDict(extra="forbid")

    outcome: Literal["complete", "partial", "noop"] | None = None
    covered_count: int = Field(default=0, ge=0, le=MAX_ENRICHMENT_ASPECTS)
    missing_count: int = Field(default=0, ge=0, le=MAX_ENRICHMENT_ASPECTS)
    regenerated_section_count: int = Field(
        default=0, ge=0, le=MAX_ENRICHMENT_ASPECTS
    )
    stale_section_count: int = Field(default=0, ge=0, le=MAX_ENRICHMENT_ASPECTS)
    limitations: list[EnrichmentLimitation] = Field(
        default_factory=list,
        max_length=MAX_LIMITATIONS_PER_RESULT,
    )


class EnrichmentActivityItem(ApiSchema):
    id: UUID
    job_type: JobType
    phase: EnrichmentActivityPhase
    status: JobStatus
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
    species_key: str | None = None
    # Every surfaced item must carry usable profile context: the accepted
    # display name and the authorized candidate id behind its link.
    scientific_name: str = Field(min_length=1)
    common_name: str | None = None
    candidate_id: UUID
    result: EnrichmentActivityResult | None = None
    last_error: ReadJobError | None = None

    @model_validator(mode="after")
    def validate_phase(self) -> Self:
        expected_phase = {
            JobType.enrich_confirmed_plant: EnrichmentActivityPhase.evidence,
            JobType.refresh_profile: EnrichmentActivityPhase.profile_refresh,
        }.get(self.job_type)

        if expected_phase is None or self.phase != expected_phase:
            raise ValueError("invalid activity job type and phase combination")

        if self.status in {JobStatus.pending, JobStatus.processing}:
            if self.completed_at is not None:
                raise ValueError("active activity cannot carry completed_at")
        elif self.completed_at is None:
            raise ValueError("terminal activity requires completed_at")
        if self.updated_at < self.created_at:
            raise ValueError("updated_at precedes created_at")
        if self.completed_at is not None and self.completed_at < self.created_at:
            raise ValueError("completed_at precedes created_at")
        if (
            self.completed_at is not None
            and self.updated_at is not None
            and self.completed_at > self.updated_at
        ):
            raise ValueError("completed_at follows updated_at")

        return self


class EnrichmentActivityResponse(ApiSchema):
    items: list[EnrichmentActivityItem] = Field(
        default_factory=list, max_length=100
    )
    has_more: bool = False
    next_cursor: str | None = None


@dataclass(frozen=True)
class EnrichmentActivityCursor:
    """Opaque keyset cursor over the stable activity ordering tuple."""

    updated_at: datetime
    job_id: UUID


def encode_enrichment_activity_cursor(
    item: EnrichmentActivityItem,
) -> str:
    payload = json.dumps(
        {
            "updated_at": item.updated_at.isoformat(),
            "id": str(item.id),
        }
    ).encode()
    return base64.urlsafe_b64encode(payload).decode().rstrip("=")


def decode_enrichment_activity_cursor(
    raw: str,
) -> EnrichmentActivityCursor | None:
    """Decode defensively; malformed cursors yield ``None`` (HTTP 422).

    Accepts only canonical urlsafe base64, exactly the two expected fields,
    and timezone-aware timestamps (normalized to UTC).
    """
    try:
        padding = "=" * (-len(raw) % 4)
        decoded = base64.b64decode(
            raw + padding,
            altchars=b"-_",
            validate=True,
        )
        payload = json.loads(decoded)
    except (ValueError, binascii.Error):
        return None
    if not isinstance(payload, dict):
        return None
    if set(payload) != {"updated_at", "id"}:
        return None
    updated_at_raw = payload["updated_at"]
    job_id_raw = payload["id"]
    if not isinstance(updated_at_raw, str) or not isinstance(job_id_raw, str):
        return None
    try:
        updated_at = datetime.fromisoformat(updated_at_raw)
        job_id = UUID(job_id_raw)
    except ValueError:
        return None
    # A cursor without zone information cannot order rows durably across
    # storage and serialization boundaries.
    if updated_at.tzinfo is None or updated_at.utcoffset() is None:
        return None
    return EnrichmentActivityCursor(
        updated_at=updated_at.astimezone(UTC),
        job_id=job_id,
    )


class EnqueueRequest(ApiSchema):
    job_type: JobType
    payload_version: int = Field(ge=1)
    payload: dict = Field(default_factory=dict)
    idempotency_key: str = Field(min_length=1, max_length=255)
    user_id: UUID | None = None
    conversation_id: UUID | None = None
    max_attempts: int = Field(default=3, ge=1)
    available_at: datetime | None = None
