"""Bounded reconciliation of legacy profiles without evidence fingerprints.

Evaluates fingerprint-less profiles against current evidence coverage in a
bounded batch, prioritizes sections containing insufficient-evidence fallback
text for refresh, and keeps existing sourced sections visible until a
replacement succeeds. Safe to run repeatedly; the refresh signals collapse by
species identity and evidence fingerprint.
"""

from __future__ import annotations

import asyncio
import sys

from app.db.session import AsyncSessionLocal
from app.profile_garden.reconcile import LegacyReconciliationService


async def run_reconciliation(*, limit: int = 50) -> dict[str, object]:
    async with AsyncSessionLocal() as session:
        return await LegacyReconciliationService(session).reconcile_batch(limit=limit)


def main() -> int:
    summary = asyncio.run(run_reconciliation())
    print(
        f"evaluated {summary['evaluated']} legacy profiles; "
        f"enqueued {summary['signalled']} refresh signals"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
