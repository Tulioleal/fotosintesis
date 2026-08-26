"""Private Prometheus metrics endpoint for the worker process.

The worker does not share memory with the API process, so its metrics
registry must be exposed through a separate HTTP listener bound to
``JOBS_METRICS_HOST:JOBS_METRICS_PORT``. The implementation uses
``asyncio.start_server`` to avoid pulling FastAPI/Uvicorn into the
worker.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Callable

logger = logging.getLogger(__name__)


async def handle_metrics_request(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    *,
    render_prometheus: Callable[[], str],
    is_ready: Callable[[], bool],
) -> None:
    try:
        request = await reader.readuntil(b"\r\n\r\n")
        request_line = request.split(b"\r\n", 1)[0].split()
        path = request_line[1] if len(request_line) >= 2 else b""
        if path == b"/metrics":
            status = b"200 OK"
            content_type = b"text/plain; version=0.0.4"
            body = render_prometheus().encode("utf-8")
        elif path == b"/ready":
            ready = is_ready()
            status = b"200 OK" if ready else b"503 Service Unavailable"
            content_type = b"text/plain; charset=utf-8"
            body = b"ready\n" if ready else b"not ready\n"
        else:
            status = b"404 Not Found"
            content_type = b"text/plain; charset=utf-8"
            body = b"not found\n"
        writer.write(
            b"HTTP/1.1 " + status + b"\r\n"
            b"Content-Type: " + content_type + b"\r\n"
            + f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
            + body
        )
        await writer.drain()
    except (asyncio.IncompleteReadError, ConnectionResetError):
        pass
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:  # noqa: BLE001
            pass


async def start_metrics_server(
    *,
    host: str,
    port: int,
    render_prometheus: Callable[[], str],
    is_ready: Callable[[], bool] = lambda: True,
) -> asyncio.AbstractServer | None:
    """Start the private metrics server. Returns the server, or None on failure."""
    try:
        server = await asyncio.start_server(
            lambda r, w: handle_metrics_request(
                r,
                w,
                render_prometheus=render_prometheus,
                is_ready=is_ready,
            ),
            host=host,
            port=port,
        )
    except OSError:
        logger.warning(
            "worker_metrics_endpoint_unavailable",
            extra={
                "ctx_host": host,
                "ctx_port": port,
                "ctx_failure_category": "listener_bind_failed",
            },
        )
        return None
    logger.info(
        "worker_metrics_endpoint_started",
        extra={"ctx_host": host, "ctx_port": port},
    )
    return server


async def stop_metrics_server(server: asyncio.AbstractServer | None) -> None:
    if server is None:
        return
    server.close()
    try:
        await server.wait_closed()
    except Exception:  # noqa: BLE001
        pass
