from time import perf_counter
from uuid import uuid4

from fastapi import Request, Response
from starlette.middleware.base import RequestResponseEndpoint

from app.observability.logging import get_logger
from app.observability.metrics import metrics_registry
from app.observability.tracing import current_trace_id

logger = get_logger(__name__)


async def request_observability_middleware(
    request: Request, call_next: RequestResponseEndpoint
) -> Response:
    trace_id = request.headers.get("x-request-id", str(uuid4()))
    token = current_trace_id.set(trace_id)
    started_at = perf_counter()
    failed = False

    try:
        response = await call_next(request)
        failed = response.status_code >= 500
        return response
    except Exception:
        failed = True
        logger.exception(
            "request failed",
            extra={
                "ctx_trace_id": trace_id,
                "ctx_method": request.method,
                "ctx_path": request.url.path,
            },
        )
        raise
    finally:
        latency = perf_counter() - started_at
        metrics_registry.record_request(latency_seconds=latency, failed=failed)
        logger.info(
            "request completed",
            extra={
                "ctx_trace_id": trace_id,
                "ctx_method": request.method,
                "ctx_path": request.url.path,
                "ctx_latency_seconds": round(latency, 6),
                "ctx_failed": failed,
            },
        )
        current_trace_id.reset(token)
