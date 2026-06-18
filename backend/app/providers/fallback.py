from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from app.observability.logging import get_logger
from app.observability.metrics import metrics_registry

logger = get_logger(__name__)


class ProviderRole(str, Enum):
    model = "model"
    judge = "judge"
    search = "search"
    vision = "vision"


class Operation(str, Enum):
    generate_text = "generate_text"
    generate_json = "generate_json"
    judge_response = "judge_response"
    search = "search"
    analyze_image = "analyze_image"


class FailureCategory(str, Enum):
    timeout = "timeout"
    rate_limit = "rate_limit"
    service_unavailable = "service_unavailable"
    network_error = "network_error"
    empty_response = "empty_response"
    invalid_structured_output = "invalid_structured_output"
    unusable_search_output = "unusable_search_output"
    non_transient = "non_transient"
    unknown = "unknown"


@dataclass
class AttemptMetadata:
    provider: str
    role: str
    operation: str
    attempt_index: int
    latency_seconds: float = 0.0
    outcome: str = "attempted"
    failure_category: str | None = None
    skipped_unhealthy: bool = False


@dataclass
class ProviderFallbackMetadata:
    role: str
    operation: str
    attempts: list[AttemptMetadata] = field(default_factory=list)
    final_provider: str | None = None
    success: bool = False


def classify_failure(exception: Exception) -> FailureCategory:
    exc_str = str(exception).lower()
    exc_type = type(exception).__name__.lower()

    if "timeout" in exc_type or "timeout" in exc_str:
        return FailureCategory.timeout
    if "rate limit" in exc_str or "rate_limit" in exc_str or "ratelimit" in exc_str:
        return FailureCategory.rate_limit
    if "unavailable" in exc_str or "503" in exc_str or "502" in exc_str:
        return FailureCategory.service_unavailable
    if "network" in exc_type or "connection" in exc_type or "connection" in exc_str:
        return FailureCategory.network_error
    if _is_timeout_error(exc_type, exc_str):
        return FailureCategory.timeout
    if "not valid json" in exc_str or "invalid json" in exc_str or "invalid structured" in exc_str:
        return FailureCategory.invalid_structured_output
    if "empty" in exc_str and ("response" in exc_str or "result" in exc_str):
        return FailureCategory.empty_response
    if "unusable search" in exc_str or "no usable" in exc_str:
        return FailureCategory.unusable_search_output

    return FailureCategory.unknown


def _is_timeout_error(exc_type: str, exc_str: str) -> bool:
    return "timeout" in exc_str or "deadline" in exc_str or "timed out" in exc_str


def is_transient_failure(category: FailureCategory) -> bool:
    return category in (
        FailureCategory.timeout,
        FailureCategory.rate_limit,
        FailureCategory.service_unavailable,
        FailureCategory.network_error,
        FailureCategory.empty_response,
        FailureCategory.invalid_structured_output,
        FailureCategory.unusable_search_output,
    )


def is_circuit_breaker_failure(category: FailureCategory) -> bool:
    return category in (
        FailureCategory.timeout,
        FailureCategory.rate_limit,
        FailureCategory.service_unavailable,
        FailureCategory.network_error,
    )


def _circuit_key(provider: str, role: str, operation: str) -> str:
    return f"{role}:{provider}:{operation}"


class CircuitBreaker:
    def __init__(self) -> None:
        self._open_until: dict[str, float] = {}

    def is_open(self, provider: str, role: str, operation: str) -> bool:
        key = _circuit_key(provider, role, operation)
        expiry = self._open_until.get(key)
        if expiry is None:
            return False
        if time.monotonic() >= expiry:
            del self._open_until[key]
            return False
        return True

    def open(self, provider: str, role: str, operation: str, duration_seconds: float) -> None:
        key = _circuit_key(provider, role, operation)
        self._open_until[key] = time.monotonic() + duration_seconds
        metrics_registry.circuit_breaker_opens_total += 1
        logger.info(
            "circuit_breaker_opened",
            extra={
                "ctx_provider": provider,
                "ctx_role": role,
                "ctx_operation": operation,
                "ctx_duration_seconds": duration_seconds,
            },
        )

    def reset(self, provider: str, role: str, operation: str) -> None:
        key = _circuit_key(provider, role, operation)
        self._open_until.pop(key, None)

    def clear(self) -> None:
        self._open_until.clear()


circuit_breaker = CircuitBreaker()
