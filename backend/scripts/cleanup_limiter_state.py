"""Bounded opportunistic cleanup of expired limiter windows.

Provides an idempotent, bounded maintenance operation that can run as a
scheduled maintenance command. It removes expired limiter state in bounded
batches without ever touching active windows.
"""

from __future__ import annotations

import asyncio
import sys

from app.core.settings import get_settings
from app.db.session import AsyncSessionLocal
from app.limiter.repository import LimiterRepository


async def run_cleanup(*, batch_size: int | None = None, max_batches: int = 20) -> int:
    settings = get_settings()
    size = batch_size or settings.auth_limiter_cleanup_batch_size
    retention_seconds = settings.auth_limiter_retention_seconds
    removed = 0
    for _ in range(max_batches):
        async with AsyncSessionLocal() as session:
            repository = LimiterRepository(session)
            batch_removed = await repository.cleanup(
                batch_size=size, retention_seconds=retention_seconds
            )
        removed += batch_removed
        if batch_removed < size:
            break
    return removed


def main() -> int:
    async def _run() -> int:
        return await run_cleanup()

    removed = asyncio.run(_run())
    print(f"removed {removed} expired limiter rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
