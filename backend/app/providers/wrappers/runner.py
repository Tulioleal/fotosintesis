"""Shared provider fallback chain runner.

The runner implements the sequential provider fallback loop used by
each adapter wrapper. It preserves the current provider ordering,
diagnostics, and failure semantics, and exposes a single hook for
callers that need to recognise unusable results (such as empty search
output) without coupling the runner to a specific capability.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from time import perf_counter
from typing import Any, TypeVar

from app.observability.metrics import metrics_registry
from app.providers.fallback import (
    AttemptMetadata,
    ProviderFallbackMetadata,
    classify_failure,
    is_transient_failure,
)
from app.providers.wrappers.exceptions import (
    AllProvidersFailedError,
    _NonTransientProviderError,
    _ProviderAttemptError,
    _UnusableSearchOutputError,
)
from app.providers.wrappers.observability import (
    classify_and_record_failure,
    log_fallback_event,
    open_circuit_if_needed,
    record_fallback_success,
    record_skipped_metadata,
    record_success_metrics,
)

T = TypeVar("T")


UnusableResultHook = Callable[[Any, str, int], _UnusableSearchOutputError | None]


def _default_unusable_hook(result: Any, provider: str, index: int) -> _UnusableSearchOutputError | None:
    return None


async def _run_with_timeout(
    call: Callable[[], Awaitable[T]],
    timeout: float | None,
) -> tuple[T, float]:
    metrics_registry.fallback_attempts_total += 1
    started_at = perf_counter()
    try:
        if timeout is not None:
            result = await asyncio.wait_for(call(), timeout=timeout)
        else:
            result = await call()
        latency = perf_counter() - started_at
        return result, latency
    except Exception as exc:
        latency = perf_counter() - started_at
        raise _ProviderAttemptError(exc, latency) from exc


def _check_circuit_breaker(provider_name: str, role: str, operation: str) -> bool:
    from app.providers.fallback import circuit_breaker
    return circuit_breaker.is_open(provider_name, role, operation)


def _raise_all_providers_failed(metadata: ProviderFallbackMetadata) -> None:
    log_fallback_event(
        "all_providers_failed",
        provider="",
        role=metadata.role,
        operation=metadata.operation,
        attempt_count=len(metadata.attempts),
    )
    raise AllProvidersFailedError(metadata)


def _raise_non_transient(
    exc: Exception,
    *,
    provider: str,
    role: str,
    operation: str,
    attempt_index: int,
    metadata: ProviderFallbackMetadata,
    latency: float | None = None,
) -> None:
    log_fallback_event(
        "non_transient_failure",
        provider=provider,
        role=role,
        operation=operation,
        attempt_index=attempt_index,
        latency=latency,
    )
    if metadata.attempts and metadata.attempts[-1].provider == provider:
        metadata.attempts[-1].outcome = "non_transient"
    else:
        metadata.attempts.append(
            AttemptMetadata(
                provider=provider,
                role=role,
                operation=operation,
                attempt_index=attempt_index,
                outcome="non_transient",
            )
        )
    metadata.final_provider = None
    metadata.success = False
    record_fallback_success(metadata)
    raise _NonTransientProviderError(metadata) from exc


async def run_provider_chain(
    *,
    providers: list[Any],
    operation: str,
    role: str,
    call: Callable[[Any], Awaitable[T]],
    attempt_timeout: float | None = None,
    circuit_breaker_duration: float | None = None,
    unusable_result_hook: UnusableResultHook | None = None,
) -> T:
    """Run ``call`` against each provider in order, falling back on failure.

    - Each provider's ``provider_name`` attribute is used for diagnostics.
    - Unusable results are reported by ``unusable_result_hook``: returning
      an :class:`_UnusableSearchOutputError` causes the runner to record a
      failed attempt and continue with the next provider.
    - On the first non-transient failure, the runner raises
      :class:`_NonTransientProviderError` immediately.
    - On the final failure, :class:`AllProvidersFailedError` is raised
      with the full ``ProviderFallbackMetadata`` attached.
    """
    metadata = ProviderFallbackMetadata(role=role, operation=operation)
    hook = unusable_result_hook or _default_unusable_hook
    for index, provider in enumerate(providers):
        provider_name = provider.provider_name
        if _check_circuit_breaker(provider_name, role, operation):
            metadata.attempts.append(
                record_skipped_metadata(provider_name, role, operation, index)
            )
            continue
        try:
            result, latency = await _run_with_timeout(
                lambda p=provider: call(p),
                attempt_timeout,
            )
        except _ProviderAttemptError as attempt_exc:
            exc = attempt_exc.original_exception
            elapsed = attempt_exc.latency_seconds
            category = classify_failure(exc)
            attempt_data = classify_and_record_failure(
                exc,
                provider=provider_name,
                role=role,
                operation=operation,
                attempt_index=index,
                latency=elapsed,
            )
            metadata.attempts.append(attempt_data)
            if is_transient_failure(category):
                open_circuit_if_needed(
                    exc, provider_name, role, operation, circuit_breaker_duration
                )
            else:
                _raise_non_transient(
                    exc,
                    provider=provider_name,
                    role=role,
                    operation=operation,
                    attempt_index=index,
                    metadata=metadata,
                    latency=elapsed,
                )
            continue
        unusable = hook(result, provider_name, index)
        if unusable is not None:
            attempt_metadata = AttemptMetadata(
                provider=provider_name,
                role=role,
                operation=operation,
                attempt_index=index,
                latency_seconds=0.0,
                outcome="failed:unusable_search_output",
                failure_category="unusable_search_output",
                transient=True,
                retryable=True,
            )
            classify_and_record_failure(
                unusable,
                provider=provider_name,
                role=role,
                operation=operation,
                attempt_index=index,
                latency=0.0,
            )
            metadata.attempts.append(attempt_metadata)
            continue
        attempt_metadata = AttemptMetadata(
            provider=provider_name,
            role=role,
            operation=operation,
            attempt_index=index,
            latency_seconds=latency,
            outcome="success",
        )
        metadata.attempts.append(attempt_metadata)
        metadata.final_provider = provider_name
        metadata.success = True
        record_fallback_success(metadata)
        record_success_metrics(
            provider_name, role, operation, latency, index, is_fallback=index > 0
        )
        return result
    metadata.final_provider = None
    metadata.success = False
    record_fallback_success(metadata)
    _raise_all_providers_failed(metadata)
