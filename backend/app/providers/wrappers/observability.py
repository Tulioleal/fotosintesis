"""Shared fallback metrics, logging, and observability helpers."""

from __future__ import annotations

from time import perf_counter
from typing import Any

from app.observability.logging import get_logger
from app.observability.metrics import metrics_registry
from app.observability.tracing import get_trace_id
from app.providers.fallback import (
    AttemptMetadata,
    ProviderFallbackMetadata,
    classify_failure,
    extract_cause_type,
    extract_status_code,
    is_transient_failure,
)
from app.providers.fallback_context import record_provider_fallback
from app.providers.fallback import circuit_breaker
from app.providers.wrappers.exceptions import _ProviderAttemptError

logger = get_logger(__name__)


def record_fallback_success(metadata: ProviderFallbackMetadata) -> None:
    record_provider_fallback(
        {
            "role": metadata.role,
            "operation": metadata.operation,
            "final_provider": metadata.final_provider,
            "success": metadata.success,
            "attempted_providers": [
                {
                    "provider": a.provider,
                    "attempt_index": a.attempt_index,
                    "outcome": a.outcome,
                    "failure_category": a.failure_category,
                    "skipped_unhealthy": a.skipped_unhealthy,
                    "transient": a.transient,
                    "retryable": a.retryable,
                    "status_code": a.status_code,
                    "cause_type": a.cause_type,
                }
                for a in metadata.attempts
            ],
        }
    )


def log_fallback_event(
    event: str,
    *,
    provider: str,
    role: str,
    operation: str,
    attempt_index: int | None = None,
    latency: float | None = None,
    failure_category: str | None = None,
    **extra: Any,
) -> None:
    logger.info(
        f"provider_fallback_{event}",
        extra={
            "ctx_trace_id": get_trace_id(),
            "ctx_provider": provider,
            "ctx_role": role,
            "ctx_operation": operation,
            "ctx_attempt_index": attempt_index,
            "ctx_latency_seconds": round(latency, 6) if latency is not None else None,
            "ctx_failure_category": failure_category,
            **extra,
        },
    )


def record_skipped_metadata(
    provider: str, role: str, operation: str, attempt_index: int
) -> AttemptMetadata:
    metrics_registry.skipped_unhealthy_providers_total += 1
    log_fallback_event(
        "skipped_unhealthy",
        provider=provider,
        role=role,
        operation=operation,
        attempt_index=attempt_index,
    )
    return AttemptMetadata(
        provider=provider,
        role=role,
        operation=operation,
        attempt_index=attempt_index,
        outcome="skipped_unhealthy",
        skipped_unhealthy=True,
    )


def record_success_metrics(
    provider: str,
    role: str,
    operation: str,
    latency: float,
    attempt_index: int,
    is_fallback: bool,
) -> None:
    metrics_registry.provider_calls_total += 1
    if is_fallback:
        metrics_registry.fallback_successes_total += 1
        log_fallback_event(
            "fallback_success",
            provider=provider,
            role=role,
            operation=operation,
            attempt_index=attempt_index,
            latency=latency,
            fallback_occurred=True,
        )


def classify_and_record_failure(
    exc: Exception,
    *,
    provider: str,
    role: str,
    operation: str,
    attempt_index: int,
    latency: float,
) -> AttemptMetadata:
    category = classify_failure(exc)
    transient = is_transient_failure(category)
    retryable = transient
    metrics_registry.record_provider_failure(
        role=role,
        provider=provider,
        operation=operation,
        failure_category=category.value,
    )
    outcome = f"failed:{category.value}"
    log_fallback_event(
        "attempt_failed",
        provider=provider,
        role=role,
        operation=operation,
        attempt_index=attempt_index,
        latency=latency,
        failure_category=category.value,
    )
    return AttemptMetadata(
        provider=provider,
        role=role,
        operation=operation,
        attempt_index=attempt_index,
        latency_seconds=latency,
        outcome=outcome,
        failure_category=category.value,
        transient=transient,
        retryable=retryable,
        status_code=extract_status_code(exc),
        cause_type=extract_cause_type(exc),
    )


def open_circuit_if_needed(
    exc: Exception,
    provider: str,
    role: str,
    operation: str,
    circuit_breaker_duration: float | None,
) -> None:
    if not circuit_breaker_duration:
        return
    category = classify_failure(exc)
    if circuit_breaker.is_open(provider, role, operation):
        return
    from app.providers.fallback import is_circuit_breaker_failure as _is_cb
    if _is_cb(category):
        circuit_breaker.open(provider, role, operation, circuit_breaker_duration)


def mark_attempt_started() -> float:
    metrics_registry.fallback_attempts_total += 1
    return perf_counter()


def wrap_attempt_error(exc: Exception, latency: float) -> _ProviderAttemptError:
    return _ProviderAttemptError(exc, latency)
