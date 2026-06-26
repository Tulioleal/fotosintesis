from collections.abc import Awaitable, Callable
from time import perf_counter
from typing import TypeVar

from app.observability.logging import get_logger
from app.observability.metrics import metrics_registry
from app.observability.tracing import get_trace_id

T = TypeVar("T")
logger = get_logger(__name__)


async def log_provider_call(
    provider: str,
    operation: str,
    call: Callable[[], Awaitable[T]],
    *,
    role: str | None = None,
) -> T:
    started_at = perf_counter()
    try:
        result = await call()
        metrics_registry.provider_calls_total += 1
        logger.info(
            "provider call completed",
            extra={
                "ctx_trace_id": get_trace_id(),
                "ctx_provider": provider,
                "ctx_role": role,
                "ctx_operation": operation,
                "ctx_latency_seconds": round(perf_counter() - started_at, 6),
            },
        )
        return result
    except Exception:
        metrics_registry.provider_calls_total += 1
        logger.exception(
            "provider call failed",
            extra={
                "ctx_trace_id": get_trace_id(),
                "ctx_provider": provider,
                "ctx_role": role,
                "ctx_operation": operation,
                "ctx_latency_seconds": round(perf_counter() - started_at, 6),
            },
        )
        raise
