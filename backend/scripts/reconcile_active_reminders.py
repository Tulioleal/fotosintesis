"""Idempotent reconciliation of garden plant active reminder counters.

Recomputes each garden plant's ``active_reminders`` value from its pending
reminder rows. Safe to run repeatedly; running again has no additional effect.
Use it to repair counters that drifted out of sync with the pending rows.
"""

from __future__ import annotations

import asyncio
import sys

from app.db.session import AsyncSessionLocal
from app.reminders.repository import ReminderRepository


async def run_reconciliation() -> int:
    async with AsyncSessionLocal() as session:
        repository = ReminderRepository(session)
        changed = await repository.reconcile_active_reminders()
    return changed


def main() -> int:
    changed = asyncio.run(run_reconciliation())
    print(f"reconciled active reminder counters for {changed} garden plants")
    return 0


if __name__ == "__main__":
    sys.exit(main())
