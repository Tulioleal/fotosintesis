from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from time import perf_counter
from typing import Any, TypeVar

from app.observability.logging import get_logger
from app.observability.metrics import metrics_registry
from app.observability.tracing import get_trace_id
from app.providers.fallback import (
    AttemptMetadata,
    ProviderFallbackMetadata,
    ProviderRole,
    circuit_breaker,
    classify_failure,
    extract_cause_type,
    extract_status_code,
    is_circuit_breaker_failure,
    is_transient_failure,
)
from app.providers.fallback_context import record_provider_fallback
from app.providers.interfaces import (
    ImageAnalysisProvider,
    JudgeEvaluationProvider,
    ModelProvider,
    SearchProvider,
)
from app.providers.types import (
    ImageAnalysisResult,
    JudgeResult,
    JsonGenerationResult,
    SearchResult,
    TextGenerationResult,
)

T = TypeVar("T")
logger = get_logger(__name__)


def _record_fallback_success(
    metadata: ProviderFallbackMetadata,
) -> None:
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


def _log_fallback_event(
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


async def _run_with_timeout(
    call: Callable[[], Awaitable[T]],
    timeout: float | None,
    provider: str,
    role: str,
    operation: str,
    attempt_index: int,
) -> tuple[T, AttemptMetadata, float]:
    metrics_registry.fallback_attempts_total += 1
    started_at = perf_counter()
    latency = 0.0
    try:
        if timeout is not None:
            result = await asyncio.wait_for(call(), timeout=timeout)
        else:
            result = await call()
        latency = perf_counter() - started_at
        return result, AttemptMetadata(
            provider=provider,
            role=role,
            operation=operation,
            attempt_index=attempt_index,
            latency_seconds=latency,
            outcome="success",
        ), latency
    except asyncio.TimeoutError as exc:
        latency = perf_counter() - started_at
        raise _ProviderAttemptError(exc, latency) from exc
    except Exception as exc:
        latency = perf_counter() - started_at
        raise _ProviderAttemptError(exc, latency) from exc


def _classify_and_record_failure(
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
    _log_fallback_event(
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


def _record_skipped_metadata(
    provider: str, role: str, operation: str, attempt_index: int
) -> AttemptMetadata:
    metrics_registry.skipped_unhealthy_providers_total += 1
    _log_fallback_event(
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


def _record_success_metrics(
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
        _log_fallback_event(
            "fallback_success",
            provider=provider,
            role=role,
            operation=operation,
            attempt_index=attempt_index,
            latency=latency,
            fallback_occurred=True,
        )


def _check_circuit_breaker(
    provider: str, role: str, operation: str, attempt_index: int
) -> bool:
    return circuit_breaker.is_open(provider, role, operation)


def _open_circuit_if_needed(
    exc: Exception,
    provider: str,
    role: str,
    operation: str,
    circuit_breaker_duration: float | None,
) -> None:
    if not circuit_breaker_duration:
        return
    category = classify_failure(exc)
    if is_circuit_breaker_failure(category):
        circuit_breaker.open(provider, role, operation, circuit_breaker_duration)

class ModelProviderFallbackWrapper(ModelProvider):
    def __init__(
        self,
        providers: list[ModelProvider],
        *,
        role: str = "model",
        attempt_timeout: float | None = None,
        circuit_breaker_duration: float | None = None,
    ) -> None:
        self._providers = providers
        self._role = role
        self._attempt_timeout = attempt_timeout
        self._circuit_breaker_duration = circuit_breaker_duration

    async def generate_text(self, prompt: str, **kwargs: Any) -> TextGenerationResult:
        metadata = ProviderFallbackMetadata(role=self._role, operation="generate_text")
        for index, provider in enumerate(self._providers):
            if _check_circuit_breaker(
                provider.provider_name, self._role, "generate_text", index
            ):
                metadata.attempts.append(_record_skipped_metadata(
                    provider.provider_name, self._role, "generate_text", index
                ))
                continue
            try:
                result, attempt, latency = await _run_with_timeout(
                    lambda p=provider: p.generate_text(prompt, **kwargs),
                    self._attempt_timeout,
                    provider.provider_name,
                    self._role,
                    "generate_text",
                    index,
                )
                metadata.attempts.append(attempt)
                metadata.final_provider = provider.provider_name
                metadata.success = True
                _record_fallback_success(metadata)
                _record_success_metrics(
                    provider.provider_name, self._role, "generate_text",
                    latency, index, is_fallback=index > 0
                )
                return result
            except _ProviderAttemptError as attempt_exc:
                exc = attempt_exc.original_exception
                elapsed = attempt_exc.latency_seconds
                category = classify_failure(exc)
                attempt_data = _classify_and_record_failure(
                    exc,
                    provider=provider.provider_name,
                    role=self._role,
                    operation="generate_text",
                    attempt_index=index,
                    latency=elapsed,
                )
                metadata.attempts.append(attempt_data)
                if is_transient_failure(category):
                    _open_circuit_if_needed(
                        exc, provider.provider_name, self._role,
                        "generate_text", self._circuit_breaker_duration
                    )
                else:
                    _raise_non_transient(
                        exc,
                        provider=provider.provider_name,
                        role=self._role,
                        operation="generate_text",
                        attempt_index=index,
                        metadata=metadata,
                        latency=elapsed,
                    )
        metadata.final_provider = None
        metadata.success = False
        _record_fallback_success(metadata)
        _raise_all_providers_failed(metadata)

    async def generate_json(
        self, prompt: str, schema: dict[str, Any], **kwargs: Any
    ) -> JsonGenerationResult:
        metadata = ProviderFallbackMetadata(role=self._role, operation="generate_json")
        for index, provider in enumerate(self._providers):
            if _check_circuit_breaker(
                provider.provider_name, self._role, "generate_json", index
            ):
                metadata.attempts.append(_record_skipped_metadata(
                    provider.provider_name, self._role, "generate_json", index
                ))
                continue
            try:
                result, attempt, latency = await _run_with_timeout(
                    lambda p=provider: p.generate_json(prompt, schema, **kwargs),
                    self._attempt_timeout,
                    provider.provider_name,
                    self._role,
                    "generate_json",
                    index,
                )
                metadata.attempts.append(attempt)
                metadata.final_provider = provider.provider_name
                metadata.success = True
                _record_fallback_success(metadata)
                _record_success_metrics(
                    provider.provider_name, self._role, "generate_json",
                    latency, index, is_fallback=index > 0
                )
                return result
            except _ProviderAttemptError as attempt_exc:
                exc = attempt_exc.original_exception
                elapsed = attempt_exc.latency_seconds
                category = classify_failure(exc)
                attempt_data = _classify_and_record_failure(
                    exc,
                    provider=provider.provider_name,
                    role=self._role,
                    operation="generate_json",
                    attempt_index=index,
                    latency=elapsed,
                )
                metadata.attempts.append(attempt_data)
                if is_transient_failure(category):
                    if category.value in ("invalid_structured_output", "empty_response"):
                        retry_result = await self._retry_generate_json(
                            provider, prompt, schema, index, metadata, **kwargs
                        )
                        if retry_result is not None:
                            return retry_result
                    _open_circuit_if_needed(
                        exc, provider.provider_name, self._role,
                        "generate_json", self._circuit_breaker_duration
                    )
                else:
                    _raise_non_transient(
                        exc,
                        provider=provider.provider_name,
                        role=self._role,
                        operation="generate_json",
                        attempt_index=index,
                        metadata=metadata,
                        latency=elapsed,
                    )
        metadata.final_provider = None
        metadata.success = False
        _raise_all_providers_failed(metadata)

    async def _retry_generate_json(
        self,
        provider: ModelProvider,
        prompt: str,
        schema: dict[str, Any],
        index: int,
        metadata: ProviderFallbackMetadata,
        **kwargs: Any,
    ) -> JsonGenerationResult | None:
        try:
            result, attempt, latency = await _run_with_timeout(
                lambda p=provider: p.generate_json(prompt, schema, **kwargs),
                self._attempt_timeout,
                provider.provider_name,
                self._role,
                "generate_json",
                index,
            )
            metadata.attempts.append(attempt)
            metadata.final_provider = provider.provider_name
            metadata.success = True
            _record_fallback_success(metadata)
            _record_success_metrics(
                provider.provider_name, self._role, "generate_json",
                latency, index, is_fallback=True
            )
            return result
        except _ProviderAttemptError as attempt_exc:
            retry_exc = attempt_exc.original_exception
            elapsed = attempt_exc.latency_seconds
            retry_category = classify_failure(retry_exc)
            attempt_data = _classify_and_record_failure(
                retry_exc,
                provider=provider.provider_name,
                role=self._role,
                operation="generate_json",
                attempt_index=index,
                latency=elapsed,
            )
            metadata.attempts.append(attempt_data)
            if not is_transient_failure(retry_category):
                _raise_non_transient(
                    retry_exc,
                    provider=provider.provider_name,
                    role=self._role,
                    operation="generate_json",
                    attempt_index=index,
                    metadata=metadata,
                    latency=elapsed,
                )
            return None

    async def judge_response(
        self, payload: dict[str, Any], rubric: dict[str, Any], **kwargs: Any
    ) -> JudgeResult:
        return await self._judge_with_fallback(payload, rubric, **kwargs)

    async def _judge_with_fallback(
        self, payload: dict[str, Any], rubric: dict[str, Any], **kwargs: Any
    ) -> JudgeResult:
        metadata = ProviderFallbackMetadata(role=self._role, operation="judge_response")
        for index, provider in enumerate(self._providers):
            if _check_circuit_breaker(
                provider.provider_name, self._role, "judge_response", index
            ):
                metadata.attempts.append(_record_skipped_metadata(
                    provider.provider_name, self._role, "judge_response", index
                ))
                continue
            try:
                result, attempt, latency = await _run_with_timeout(
                    lambda p=provider: p.judge_response(payload, rubric, **kwargs),
                    self._attempt_timeout,
                    provider.provider_name,
                    self._role,
                    "judge_response",
                    index,
                )
                metadata.attempts.append(attempt)
                metadata.final_provider = provider.provider_name
                metadata.success = True
                _record_fallback_success(metadata)
                _record_success_metrics(
                    provider.provider_name, self._role, "judge_response",
                    latency, index, is_fallback=index > 0
                )
                return result
            except _ProviderAttemptError as attempt_exc:
                exc = attempt_exc.original_exception
                elapsed = attempt_exc.latency_seconds
                category = classify_failure(exc)
                attempt_data = _classify_and_record_failure(
                    exc,
                    provider=provider.provider_name,
                    role=self._role,
                    operation="judge_response",
                    attempt_index=index,
                    latency=elapsed,
                )
                metadata.attempts.append(attempt_data)
                if is_transient_failure(category):
                    _open_circuit_if_needed(
                        exc, provider.provider_name, self._role,
                        "judge_response", self._circuit_breaker_duration
                    )
                else:
                    _raise_non_transient(
                        exc,
                        provider=provider.provider_name,
                        role=self._role,
                        operation="judge_response",
                        attempt_index=index,
                        metadata=metadata,
                        latency=elapsed,
                    )
        metadata.final_provider = None
        metadata.success = False
        _raise_all_providers_failed(metadata)

    def _get_providers_for_judge(self) -> list:
        return self._providers


class JudgeEvaluationProviderFallbackWrapper(JudgeEvaluationProvider):
    def __init__(
        self,
        providers: list[JudgeEvaluationProvider],
        *,
        role: str = "judge",
        attempt_timeout: float | None = None,
        circuit_breaker_duration: float | None = None,
    ) -> None:
        self._providers = providers
        self._role = role
        self._attempt_timeout = attempt_timeout
        self._circuit_breaker_duration = circuit_breaker_duration

    async def judge_response(
        self, payload: dict[str, Any], rubric: dict[str, Any], **kwargs: Any
    ) -> JudgeResult:
        metadata = ProviderFallbackMetadata(role=self._role, operation="judge_response")
        for index, provider in enumerate(self._providers):
            if _check_circuit_breaker(
                provider.provider_name, self._role, "judge_response", index
            ):
                metadata.attempts.append(_record_skipped_metadata(
                    provider.provider_name, self._role, "judge_response", index
                ))
                continue
            try:
                result, attempt, latency = await _run_with_timeout(
                    lambda p=provider: p.judge_response(payload, rubric, **kwargs),
                    self._attempt_timeout,
                    provider.provider_name,
                    self._role,
                    "judge_response",
                    index,
                )
                metadata.attempts.append(attempt)
                metadata.final_provider = provider.provider_name
                metadata.success = True
                _record_fallback_success(metadata)
                _record_success_metrics(
                    provider.provider_name, self._role, "judge_response",
                    latency, index, is_fallback=index > 0
                )
                return result
            except _ProviderAttemptError as attempt_exc:
                exc = attempt_exc.original_exception
                elapsed = attempt_exc.latency_seconds
                category = classify_failure(exc)
                attempt_data = _classify_and_record_failure(
                    exc,
                    provider=provider.provider_name,
                    role=self._role,
                    operation="judge_response",
                    attempt_index=index,
                    latency=elapsed,
                )
                metadata.attempts.append(attempt_data)
                if is_transient_failure(category):
                    if category.value in ("invalid_structured_output", "empty_response"):
                        retry_result = await self._retry_judge_response(
                            provider, payload, rubric, index, metadata, **kwargs
                        )
                        if retry_result is not None:
                            return retry_result
                    _open_circuit_if_needed(
                        exc, provider.provider_name, self._role,
                        "judge_response", self._circuit_breaker_duration
                    )
                else:
                    _raise_non_transient(
                        exc,
                        provider=provider.provider_name,
                        role=self._role,
                        operation="judge_response",
                        attempt_index=index,
                        metadata=metadata,
                        latency=elapsed,
                    )
        metadata.final_provider = None
        metadata.success = False
        _record_fallback_success(metadata)
        _raise_all_providers_failed(metadata)

    async def _retry_judge_response(
        self,
        provider: JudgeEvaluationProvider,
        payload: dict[str, Any],
        rubric: dict[str, Any],
        index: int,
        metadata: ProviderFallbackMetadata,
        **kwargs: Any,
    ) -> JudgeResult | None:
        try:
            result, attempt, latency = await _run_with_timeout(
                lambda p=provider: p.judge_response(payload, rubric, **kwargs),
                self._attempt_timeout,
                provider.provider_name,
                self._role,
                "judge_response",
                index,
            )
            metadata.attempts.append(attempt)
            metadata.final_provider = provider.provider_name
            metadata.success = True
            _record_fallback_success(metadata)
            _record_success_metrics(
                provider.provider_name, self._role, "judge_response",
                latency, index, is_fallback=True
            )
            return result
        except _ProviderAttemptError as attempt_exc:
            retry_exc = attempt_exc.original_exception
            elapsed = attempt_exc.latency_seconds
            retry_category = classify_failure(retry_exc)
            attempt_data = _classify_and_record_failure(
                retry_exc,
                provider=provider.provider_name,
                role=self._role,
                operation="judge_response",
                attempt_index=index,
                latency=elapsed,
            )
            metadata.attempts.append(attempt_data)
            if not is_transient_failure(retry_category):
                _raise_non_transient(
                    retry_exc,
                    provider=provider.provider_name,
                    role=self._role,
                    operation="judge_response",
                    attempt_index=index,
                    metadata=metadata,
                    latency=elapsed,
                )
            return None


class SearchProviderFallbackWrapper(SearchProvider):
    def __init__(
        self,
        providers: list[SearchProvider],
        *,
        role: str = "search",
        attempt_timeout: float | None = None,
        circuit_breaker_duration: float | None = None,
    ) -> None:
        self._providers = providers
        self._role = role
        self._attempt_timeout = attempt_timeout
        self._circuit_breaker_duration = circuit_breaker_duration

    async def search(self, query: str, **kwargs: Any) -> list[SearchResult]:
        metadata = ProviderFallbackMetadata(role=self._role, operation="search")
        for index, provider in enumerate(self._providers):
            if _check_circuit_breaker(
                provider.provider_name, self._role, "search", index
            ):
                metadata.attempts.append(_record_skipped_metadata(
                    provider.provider_name, self._role, "search", index
                ))
                continue
            try:
                result, attempt, latency = await _run_with_timeout(
                    lambda p=provider: p.search(query, **kwargs),
                    self._attempt_timeout,
                    provider.provider_name,
                    self._role,
                    "search",
                    index,
                )
                if not result:
                    raise _UnusableSearchOutputError(f"{provider.provider_name} returned no results")
                metadata.attempts.append(attempt)
                metadata.final_provider = provider.provider_name
                metadata.success = True
                _record_fallback_success(metadata)
                _record_success_metrics(
                    provider.provider_name, self._role, "search",
                    latency, index, is_fallback=index > 0
                )
                return result
            except _UnusableSearchOutputError:
                attempt_data = _classify_and_record_failure(
                    Exception("unusable search output"),
                    provider=provider.provider_name,
                    role=self._role,
                    operation="search",
                    attempt_index=index,
                    latency=attempt.latency_seconds,
                )
                metadata.attempts.append(attempt_data)
                continue
            except _ProviderAttemptError as attempt_exc:
                exc = attempt_exc.original_exception
                elapsed = attempt_exc.latency_seconds
                category = classify_failure(exc)
                attempt_data = _classify_and_record_failure(
                    exc,
                    provider=provider.provider_name,
                    role=self._role,
                    operation="search",
                    attempt_index=index,
                    latency=elapsed,
                )
                metadata.attempts.append(attempt_data)
                if is_transient_failure(category):
                    _open_circuit_if_needed(
                        exc, provider.provider_name, self._role,
                        "search", self._circuit_breaker_duration
                    )
                else:
                    _raise_non_transient(
                        exc,
                        provider=provider.provider_name,
                        role=self._role,
                        operation="search",
                        attempt_index=index,
                        metadata=metadata,
                        latency=elapsed,
                    )
        metadata.final_provider = None
        metadata.success = False
        _raise_all_providers_failed(metadata)


class ImageAnalysisProviderFallbackWrapper(ImageAnalysisProvider):
    def __init__(
        self,
        providers: list[ImageAnalysisProvider],
        *,
        role: str = "vision",
        attempt_timeout: float | None = None,
        circuit_breaker_duration: float | None = None,
    ) -> None:
        self._providers = providers
        self._role = role
        self._attempt_timeout = attempt_timeout
        self._circuit_breaker_duration = circuit_breaker_duration

    async def analyze_image(
        self, image: bytes, prompt: str | None = None, **kwargs: Any
    ) -> ImageAnalysisResult:
        metadata = ProviderFallbackMetadata(role=self._role, operation="analyze_image")
        for index, provider in enumerate(self._providers):
            if _check_circuit_breaker(
                provider.provider_name, self._role, "analyze_image", index
            ):
                metadata.attempts.append(_record_skipped_metadata(
                    provider.provider_name, self._role, "analyze_image", index
                ))
                continue
            try:
                result, attempt, latency = await _run_with_timeout(
                    lambda p=provider: p.analyze_image(image, prompt, **kwargs),
                    self._attempt_timeout,
                    provider.provider_name,
                    self._role,
                    "analyze_image",
                    index,
                )
                metadata.attempts.append(attempt)
                metadata.final_provider = provider.provider_name
                metadata.success = True
                _record_fallback_success(metadata)
                _record_success_metrics(
                    provider.provider_name, self._role, "analyze_image",
                    latency, index, is_fallback=index > 0
                )
                return result
            except _ProviderAttemptError as attempt_exc:
                exc = attempt_exc.original_exception
                elapsed = attempt_exc.latency_seconds
                category = classify_failure(exc)
                attempt_data = _classify_and_record_failure(
                    exc,
                    provider=provider.provider_name,
                    role=self._role,
                    operation="analyze_image",
                    attempt_index=index,
                    latency=elapsed,
                )
                metadata.attempts.append(attempt_data)
                if is_transient_failure(category):
                    _open_circuit_if_needed(
                        exc, provider.provider_name, self._role,
                        "analyze_image", self._circuit_breaker_duration
                    )
                else:
                    _raise_non_transient(
                        exc,
                        provider=provider.provider_name,
                        role=self._role,
                        operation="analyze_image",
                        attempt_index=index,
                        metadata=metadata,
                        latency=elapsed,
                    )
        metadata.final_provider = None
        metadata.success = False
        _record_fallback_success(metadata)
        _raise_all_providers_failed(metadata)


class _UnusableSearchOutputError(Exception):
    pass


class _ProviderAttemptError(Exception):
    """Wraps an exception from _run_with_timeout to carry elapsed latency."""

    def __init__(self, original_exception: Exception, latency_seconds: float) -> None:
        self.original_exception = original_exception
        self.latency_seconds = latency_seconds
        super().__init__(str(original_exception))


class AllProvidersFailedError(RuntimeError):
    def __init__(self, metadata: ProviderFallbackMetadata) -> None:
        self.fallback_metadata = metadata
        super().__init__(
            f"All providers failed for role={metadata.role} operation={metadata.operation}"
        )

    @property
    def is_transient(self) -> bool:
        return any(a.transient for a in self.fallback_metadata.attempts if a.failure_category)

    @property
    def is_retryable(self) -> bool:
        return self.is_transient


def _raise_all_providers_failed(metadata: ProviderFallbackMetadata) -> None:
    _log_fallback_event(
        "all_providers_failed",
        provider="",
        role=metadata.role,
        operation=metadata.operation,
        attempt_count=len(metadata.attempts),
    )
    raise AllProvidersFailedError(metadata)


class _NonTransientProviderError(AllProvidersFailedError):
    pass


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
    _log_fallback_event(
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
    _record_fallback_success(metadata)
    raise _NonTransientProviderError(metadata) from exc
