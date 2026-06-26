from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from time import perf_counter
from uuid import uuid4

from app.observability.logging import get_logger

logger = get_logger(__name__)
current_trace_id: ContextVar[str | None] = ContextVar("current_trace_id", default=None)


@dataclass(frozen=True)
class TraceSpan:
    name: str
    trace_id: str
    attributes: dict[str, str] = field(default_factory=dict)


def get_trace_id() -> str:
    trace_id = current_trace_id.get()
    if trace_id is None:
        trace_id = str(uuid4())
        current_trace_id.set(trace_id)
    return trace_id


@contextmanager
def trace_span(name: str, **attributes: str) -> Iterator[TraceSpan]:
    trace_id = get_trace_id()
    started_at = perf_counter()
    logger.info(
        "trace span started",
        extra={"ctx_trace_id": trace_id, "ctx_span": name, "ctx_attributes": attributes},
    )
    try:
        yield TraceSpan(name=name, trace_id=trace_id, attributes=attributes)
    except Exception:
        logger.exception(
            "trace span failed",
            extra={"ctx_trace_id": trace_id, "ctx_span": name, "ctx_attributes": attributes},
        )
        raise
    finally:
        elapsed = perf_counter() - started_at
        logger.info(
            "trace span finished",
            extra={
                "ctx_trace_id": trace_id,
                "ctx_span": name,
                "ctx_elapsed_seconds": round(elapsed, 6),
            },
        )
