"""PostgreSQL-backed atomic limiter state repository.

All enforcement operations use atomic upsert semantics and one transaction
per admission so concurrent replicas cannot exceed a bound and a rejected
multi-rule request never partially consumes state. Expired windows are
removed by indexed, idempotent, bounded cleanup that honors the configured
retention period.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repository import RepositoryBase
from app.limiter.policy import (
    AdmissionOutcome,
    Dimension,
    EndpointCategory,
    LimiterOutcome,
    LimiterPolicy,
)
from app.limiter.tables import limiter_state


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _window_for(now: datetime, window_seconds: int) -> tuple[datetime, datetime]:
    epoch = int(now.timestamp())
    window_start_ts = (epoch // window_seconds) * window_seconds
    window_start = datetime.fromtimestamp(window_start_ts, tz=timezone.utc)
    return window_start, window_start + timedelta(seconds=window_seconds)


class LimiterRepository(RepositoryBase):
    """Atomic shared limiter state backed by PostgreSQL (or SQLite in tests)."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def admit(
        self,
        *,
        category: EndpointCategory,
        keys: dict[Dimension, str],
        policy: LimiterPolicy,
        now: datetime | None = None,
    ) -> AdmissionOutcome:
        now = _utc(now or datetime.now(timezone.utc))
        endpoint = policy.endpoints[category]
        # Stable key order prevents deadlocks when multiple rules apply.
        ordered = sorted(keys.items(), key=lambda item: (item[0].value, item[1]))
        for dimension, digest_key in ordered:
            if dimension == Dimension.account and endpoint.account is None:
                continue
            profile = endpoint.source if dimension == Dimension.source else endpoint.account
            assert profile is not None
            window_start, window_end = _window_for(now, profile.window_seconds)
            admitted = await self._consume(
                category=category,
                dimension=dimension,
                digest_key=digest_key,
                window_start=window_start,
                window_end=window_end,
                limit=profile.limit,
                now=now,
            )
            if not admitted:
                await self.rollback()
                # Round remaining time up and never return zero during an
                # active rejection so clients do not retry immediately.
                remaining = math.ceil((window_end - now).total_seconds())
                remaining = max(remaining, 1)
                return AdmissionOutcome(
                    outcome=LimiterOutcome.rejected,
                    retry_after_seconds=min(remaining, policy.max_retry_after_seconds),
                )
        await self.commit()
        return AdmissionOutcome(outcome=LimiterOutcome.allowed)

    async def _consume(
        self,
        *,
        category: EndpointCategory,
        dimension: Dimension,
        digest_key: str,
        window_start: datetime,
        window_end: datetime,
        limit: int,
        now: datetime,
    ) -> bool:
        insert_cls = pg_insert if self.session.get_bind().dialect.name == "postgresql" else sqlite_insert
        stmt = (
            insert_cls(limiter_state)
            .values(
                id=uuid4(),
                dimension=dimension.value,
                category=category.value,
                digest_key=digest_key,
                window_start=window_start,
                window_end=window_end,
                count=1,
                created_at=now,
                updated_at=now,
            )
            .on_conflict_do_update(
                index_elements=["dimension", "category", "digest_key", "window_start"],
                set_={"count": limiter_state.c.count + 1, "updated_at": now},
                where=limiter_state.c.count < limit,
            )
            .returning(limiter_state.c.id)
        )
        row = (await self.session.execute(stmt)).first()
        return row is not None

    async def relax_account(
        self,
        *,
        category: EndpointCategory,
        account_key: str,
    ) -> None:
        """Relax only the account-specific state for ``category``.

        Only rows keyed by the account dimension for the given category are
        removed; source-wide and unrelated limits are never touched.
        """
        await self.session.execute(
            delete(limiter_state).where(
                limiter_state.c.dimension == Dimension.account.value,
                limiter_state.c.category == category.value,
                limiter_state.c.digest_key == account_key,
            )
        )
        await self.commit()

    async def cleanup(
        self,
        *,
        batch_size: int,
        retention_seconds: int,
        now: datetime | None = None,
    ) -> int:
        """Remove expired windows in bounded batches, honoring retention.

        Only rows whose window ended more than ``retention_seconds`` ago are
        removed; rows still inside the retention period are preserved so a
        freshly expired window survives until the lifecycle cutoff.
        """
        now = _utc(now or datetime.now(timezone.utc))
        cutoff = now - timedelta(seconds=retention_seconds)
        stmt = select(limiter_state.c.id).where(limiter_state.c.window_end < cutoff).limit(batch_size)
        if self.session.get_bind().dialect.name == "postgresql":
            stmt = stmt.with_for_update(skip_locked=True)
        expired_ids = (await self.session.execute(stmt)).scalars().all()
        if not expired_ids:
            return 0
        await self.session.execute(
            delete(limiter_state).where(limiter_state.c.id.in_(expired_ids))
        )
        await self.commit()
        return len(expired_ids)


__all__ = ["LimiterRepository"]
