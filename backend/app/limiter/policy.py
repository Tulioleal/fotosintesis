"""Shared limiter policy types and configuration.

The policy types are deliberately closed: endpoint categories, dimensions,
outcomes, and storage-failure modes are fixed enums so no raw account or
source identifier can ever become a metric or log label.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator

LIMITER_HEADER_SOURCE_KEY = "x-fotosintesis-source-key"
LIMITER_HEADER_SOURCE_ASSERTION = "x-fotosintesis-source-assertion"

# Any client-supplied header carrying these names is stripped by the
# frontend trust boundary before an internal request reaches the backend.
INTERNAL_LIMITER_HEADERS = frozenset(
    {LIMITER_HEADER_SOURCE_KEY, LIMITER_HEADER_SOURCE_ASSERTION}
)


class Dimension(str, Enum):
    """The dimension a limit key addresses."""

    source = "source"
    account = "account"


class EndpointCategory(str, Enum):
    """Closed endpoint categories covered by the authentication boundary."""

    registration = "registration"
    credential_verification = "credential_verification"
    recovery_initiation = "recovery_initiation"
    recovery_confirmation = "recovery_confirmation"
    authjs_post = "authjs_post"


class LimiterOutcome(str, Enum):
    """Closed limiter decision outcomes used for metrics and logging."""

    allowed = "allowed"
    rejected = "rejected"
    storage_failure = "storage_failure"


class StorageFailureMode(str, Enum):
    """How an endpoint behaves when limiter storage is unavailable.

    Only ``fail_closed`` is supported: a limiter-storage exception must never
    admit authentication work. An explicitly bounded per-process fallback was
    rejected because a process-local counter without shared admission cannot
    preserve the distributed bound.
    """

    fail_closed = "fail_closed"


class LimitProfile(BaseModel):
    """A fixed-window limit rule for one dimension of one category."""

    limit: int = Field(gt=0)
    window_seconds: int = Field(gt=0)


class AdmissionOutcome(BaseModel):
    """The bounded result of evaluating a request against the limiter."""

    outcome: LimiterOutcome
    retry_after_seconds: int = Field(default=0, ge=0)
    storage_failure: bool = False


class EndpointPolicy(BaseModel):
    """The full set of rules for one closed endpoint category."""

    source: LimitProfile
    account: LimitProfile | None = None
    storage_failure_mode: StorageFailureMode = StorageFailureMode.fail_closed


class LimiterPolicy(BaseModel):
    """Validated, closed limiter policy for every covered endpoint category.

    ``endpoints`` must contain an entry for every member of
    :class:`EndpointCategory`. Unknown categories and unsafe (non-positive)
    limits are rejected at construction time.
    """

    endpoints: dict[EndpointCategory, EndpointPolicy] = Field(default_factory=dict)
    max_retry_after_seconds: int = Field(default=3600, ge=1)
    retention_seconds: int = Field(default=24 * 3600, gt=0)
    hmac_key_version: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def _validate_covered_categories(self) -> "LimiterPolicy":
        covered = set(self.endpoints)
        required = set(EndpointCategory)
        if covered != required:
            missing = ", ".join(sorted(item.value for item in required - covered))
            extra = ", ".join(sorted(item.value for item in covered - required))
            detail = []
            if missing:
                detail.append(f"missing endpoint categories: {missing}")
            if extra:
                detail.append(f"unknown endpoint categories: {extra}")
            raise ValueError("; ".join(detail) or "invalid limiter policy")
        return self

    def for_category(self, category: EndpointCategory) -> EndpointPolicy:
        return self.endpoints[category]

    def retry_after_for_category(self, category: EndpointCategory) -> int:
        return min(self.max_retry_after_seconds, self.endpoints[category].source.window_seconds)


__all__ = [
    "AdmissionOutcome",
    "Dimension",
    "EndpointCategory",
    "EndpointPolicy",
    "INTERNAL_LIMITER_HEADERS",
    "LIMITER_HEADER_SOURCE_ASSERTION",
    "LIMITER_HEADER_SOURCE_KEY",
    "LimitProfile",
    "LimiterOutcome",
    "LimiterPolicy",
    "StorageFailureMode",
]
