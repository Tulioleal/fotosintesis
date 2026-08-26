"""PostgreSQL integration tests for distributed limiter enforcement.

Verifies atomic bounds under concurrent requests through separate repository
instances, consistent enforcement, and cleanup safety during active updates.
Requires a PostgreSQL database (see ``integration/conftest.py``).
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.limiter.policy import (
    Dimension,
    EndpointCategory,
    EndpointPolicy,
    LimitProfile,
    LimiterPolicy,
)
from app.limiter.repository import LimiterRepository
from app.limiter.tables import limiter_state


def policy_for(
    limit: int = 3,
    *,
    account_limit: int | None = None,
    window_seconds: int = 3600,
) -> LimiterPolicy:
    return LimiterPolicy(
        endpoints={
            category: EndpointPolicy(
                source=LimitProfile(limit=limit, window_seconds=window_seconds),
                account=(
                    LimitProfile(
                        limit=account_limit if account_limit is not None else limit,
                        window_seconds=window_seconds,
                    )
                    if category
                    in {
                        EndpointCategory.credential_verification,
                        EndpointCategory.recovery_initiation,
                        EndpointCategory.recovery_confirmation,
                    }
                    else None
                ),
            )
            for category in EndpointCategory
        },
        max_retry_after_seconds=3600,
        retention_seconds=86400,
    )


async def test_atomic_source_bound_holds_under_concurrent_requests(
    pg_engine: AsyncEngine,
) -> None:
    policy = policy_for(limit=3)
    digest = "concurrent-source-key"

    async def attempt() -> bool:
        async with AsyncSession(pg_engine) as session:
            repo = LimiterRepository(session)
            outcome = await repo.admit(
                category=EndpointCategory.registration,
                keys={Dimension.source: digest},
                policy=policy,
            )
            return outcome.outcome.value == "allowed"

    results = await asyncio.gather(*[attempt() for _ in range(12)])
    assert sum(results) == 3

    async with AsyncSession(pg_engine) as session:
        row = (
            await session.execute(
                select(limiter_state.c.count).where(
                    limiter_state.c.digest_key == digest,
                    limiter_state.c.dimension == Dimension.source.value,
                )
            )
        ).scalar_one()
    assert row == 3


async def test_atomic_multi_rule_bounds_both_dimensions(
    pg_engine: AsyncEngine,
) -> None:
    policy = policy_for(limit=2)
    source_key = "concurrent-source-2"
    account_key = "concurrent-account-2"

    async def attempt() -> bool:
        async with AsyncSession(pg_engine) as session:
            repo = LimiterRepository(session)
            outcome = await repo.admit(
                category=EndpointCategory.credential_verification,
                keys={Dimension.source: source_key, Dimension.account: account_key},
                policy=policy,
            )
            return outcome.outcome.value == "allowed"

    results = await asyncio.gather(*[attempt() for _ in range(10)])
    # The account rule bounds the combined attempts to 2.
    assert sum(results) == 2


async def test_rejected_multi_rule_request_does_not_partially_consume(
    pg_engine: AsyncEngine,
) -> None:
    # Asymmetric limits force a real rollback. Rules are evaluated in stable
    # key order (account before source), so the account rule is admitted
    # (mutated) first and the later source rule rejects. The transaction must
    # roll back the account consumption so no partial state survives.
    policy = policy_for(limit=2, account_limit=3)
    source_key = "rollback-source"
    account_key = "rollback-account"

    async def admit_pair() -> None:
        async with AsyncSession(pg_engine) as session:
            repo = LimiterRepository(session)
            await repo.admit(
                category=EndpointCategory.credential_verification,
                keys={Dimension.source: source_key, Dimension.account: account_key},
                policy=policy,
            )

    # Admit twice: account goes to 2, source goes to 2 (source limit is 2).
    for _ in range(2):
        await admit_pair()

    # The third request mutates the account rule (2 -> 3, under its limit of 3)
    # and then is rejected by the exhausted source rule. Rollback must undo the
    # account mutation, keeping account at 2.
    async with AsyncSession(pg_engine) as session:
        repo = LimiterRepository(session)
        outcome = await repo.admit(
            category=EndpointCategory.credential_verification,
            keys={Dimension.source: source_key, Dimension.account: account_key},
            policy=policy,
        )
        assert outcome.outcome.value == "rejected"

    async with AsyncSession(pg_engine) as session:
        source_count = (
            await session.execute(
                select(limiter_state.c.count).where(
                    limiter_state.c.digest_key == source_key,
                    limiter_state.c.dimension == Dimension.source.value,
                )
            )
        ).scalar_one()
        account_count = (
            await session.execute(
                select(limiter_state.c.count).where(
                    limiter_state.c.digest_key == account_key,
                    limiter_state.c.dimension == Dimension.account.value,
                )
            )
        ).scalar_one()
    assert source_count == 2
    assert account_count == 2


async def test_consistent_enforcement_through_separate_repository_instances(
    pg_engine: AsyncEngine,
    pg_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    policy = policy_for(limit=1)
    digest = "cross-instance-key"

    allowed = 0
    for _ in range(3):
        async with pg_session_factory() as session:
            repo = LimiterRepository(session)
            outcome = await repo.admit(
                category=EndpointCategory.registration,
                keys={Dimension.source: digest},
                policy=policy,
            )
            if outcome.outcome.value == "allowed":
                allowed += 1
    assert allowed == 1


async def test_cleanup_removes_only_expired_windows(pg_engine: AsyncEngine) -> None:
    # A small window makes the retention boundary deterministic: the 2h-old
    # row's window ended long before the retention cutoff, while the active
    # row stays.
    policy = policy_for(limit=5, window_seconds=60)
    now = datetime.now(timezone.utc)
    old_now = now - timedelta(hours=2)

    async def seed(digest: str, window_now: datetime) -> None:
        async with AsyncSession(pg_engine) as session:
            repo = LimiterRepository(session)
            await repo.admit(
                category=EndpointCategory.registration,
                keys={Dimension.source: digest},
                policy=policy,
                now=window_now,
            )

    # Seed an expired window (2h ago) and an active one (now).
    await seed("expired-window-key", old_now)
    await seed("active-window-key", now)

    async with AsyncSession(pg_engine) as session:
        repo = LimiterRepository(session)
        removed = await repo.cleanup(batch_size=10, retention_seconds=3600, now=now)
    assert removed == 1

    async with AsyncSession(pg_engine) as session:
        remaining = (
            await session.execute(
                select(func.count()).select_from(limiter_state)
            )
        ).scalar_one()
    assert remaining == 1


async def test_cleanup_is_safe_during_active_updates(pg_engine: AsyncEngine) -> None:
    policy = policy_for(limit=5, window_seconds=60)
    active_key = "active-during-cleanup"
    expired_key = "expired-during-cleanup"
    now = datetime.now(timezone.utc)

    async def seed() -> None:
        async with AsyncSession(pg_engine) as session:
            repo = LimiterRepository(session)
            # Seed one expired row far enough in the past that its window fully
            # ended beyond the retention cutoff, plus an active row.
            await repo.admit(
                category=EndpointCategory.registration,
                keys={Dimension.source: expired_key},
                policy=policy,
                now=now - timedelta(hours=2),
            )
            await repo.admit(
                category=EndpointCategory.registration,
                keys={Dimension.source: active_key},
                policy=policy,
                now=now,
            )

    await seed()

    async def admission() -> None:
        async with AsyncSession(pg_engine) as session:
            repo = LimiterRepository(session)
            await repo.admit(
                category=EndpointCategory.registration,
                keys={Dimension.source: active_key},
                policy=policy,
            )

    async def cleanup() -> None:
        async with AsyncSession(pg_engine) as session:
            repo = LimiterRepository(session)
            await repo.cleanup(batch_size=50, retention_seconds=3600)

    # Interleave concurrent admissions and cleanup; the expired row is removed
    # while the active counter remains intact and atomic.
    async def worker(round_index: int) -> None:
        if round_index % 2 == 0:
            await cleanup()
        else:
            await admission()

    await asyncio.gather(*[worker(i) for i in range(8)])

    async with AsyncSession(pg_engine) as session:
        active_count = (
            await session.execute(
                select(limiter_state.c.count).where(
                    limiter_state.c.digest_key == active_key,
                    limiter_state.c.dimension == Dimension.source.value,
                )
            )
        ).scalar_one()
        expired_exists = (
            await session.execute(
                select(limiter_state.c.id).where(
                    limiter_state.c.digest_key == expired_key,
                    limiter_state.c.dimension == Dimension.source.value,
                )
            )
        ).first()
    assert 1 <= active_count <= 5
    assert expired_exists is None
