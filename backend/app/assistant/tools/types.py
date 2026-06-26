"""Constants, dataclasses, and pure helpers used by AssistantTools."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.providers.fallback import (
    NON_RECOVERABLE_FAILURE_CATEGORIES,
    AttemptMetadata,
    ProviderFallbackMetadata,
    classify_failure,
    extract_cause_type,
    extract_status_code,
    is_transient_failure,
)
from app.providers.wrappers import AllProvidersFailedError

TRUSTED_WEB_EVIDENCE_CONFIDENCE = 0.55
EXTERNAL_FALLBACK_EVIDENCE_CONFIDENCE = 0.35
EXTERNAL_FALLBACK_VALIDATION_STATUS = "external_fallback"

NON_RECOVERABLE_CATEGORIES = NON_RECOVERABLE_FAILURE_CATEGORIES


@dataclass(frozen=True)
class ProviderFailureEntry:
    provider: str
    role: str
    operation: str
    failure_category: str | None = None
    retryable: bool = False
    transient: bool = False
    status_code: int | None = None
    cause_type: str | None = None
    attempt_index: int | None = None


@dataclass(frozen=True)
class AssistantFailureMetadata:
    failure_category: str
    retryable: bool = False
    transient: bool = False
    provider_failures: list[ProviderFailureEntry] = field(default_factory=list)


@dataclass(frozen=True)
class ToolResult:
    ok: bool
    data: object | None = None
    error: str | None = None
    failure_metadata: AssistantFailureMetadata | None = None


def sanitize_attempt(attempt: AttemptMetadata) -> ProviderFailureEntry:
    return ProviderFailureEntry(
        provider=attempt.provider,
        role=attempt.role,
        operation=attempt.operation,
        failure_category=attempt.failure_category,
        retryable=attempt.retryable,
        transient=attempt.transient,
        status_code=attempt.status_code,
        cause_type=attempt.cause_type,
        attempt_index=attempt.attempt_index,
    )


def category_from_fallback_metadata(meta: ProviderFallbackMetadata) -> str:
    non_transient = [
        a for a in meta.attempts
        if a.failure_category and a.failure_category in NON_RECOVERABLE_CATEGORIES
    ]
    if non_transient:
        return non_transient[0].failure_category
    categories = [a.failure_category for a in meta.attempts if a.failure_category]
    if categories:
        return categories[-1]
    return "unknown"


def build_assistant_failure_metadata(exc: Exception) -> AssistantFailureMetadata:
    if isinstance(exc, AllProvidersFailedError):
        meta = exc.fallback_metadata
        category = category_from_fallback_metadata(meta)
        entries = [sanitize_attempt(a) for a in meta.attempts if a.outcome != "skipped_unhealthy"]
        return AssistantFailureMetadata(
            failure_category=category,
            retryable=exc.is_retryable,
            transient=exc.is_transient,
            provider_failures=entries,
        )
    fb_category = classify_failure(exc)
    entry = ProviderFailureEntry(
        provider="",
        role="",
        operation="",
        failure_category=fb_category.value,
        retryable=is_transient_failure(fb_category),
        transient=is_transient_failure(fb_category),
        status_code=extract_status_code(exc),
        cause_type=extract_cause_type(exc),
    )
    return AssistantFailureMetadata(
        failure_category=fb_category.value,
        retryable=is_transient_failure(fb_category),
        transient=is_transient_failure(fb_category),
        provider_failures=[entry],
    )


__all__ = [
    "AssistantFailureMetadata",
    "EXTERNAL_FALLBACK_EVIDENCE_CONFIDENCE",
    "EXTERNAL_FALLBACK_VALIDATION_STATUS",
    "NON_RECOVERABLE_CATEGORIES",
    "ProviderFailureEntry",
    "ToolResult",
    "TRUSTED_WEB_EVIDENCE_CONFIDENCE",
    "build_assistant_failure_metadata",
    "category_from_fallback_metadata",
    "sanitize_attempt",
]
