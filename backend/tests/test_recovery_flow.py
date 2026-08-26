"""Backend tests for secure one-time password recovery.

Covers token hashing, one-time consumption, expiry and invalidation,
atomic confirmation (including concurrent replay), session revocation after
a reset, and redaction of the raw token from persisted records.
"""

from datetime import timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.passwords import hash_token, verify_password
from app.auth.repository import DatabaseAuthRepository
from app.auth.tables import recovery_tokens, sessions, users


@pytest.mark.asyncio
async def test_recovery_token_is_persisted_as_hash_only(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        repo = DatabaseAuthRepository(session)
        user = await repo.create_user("Tia", "tia@example.com", "password123")
        recovery = await repo.create_recovery_token("tia@example.com", ttl=timedelta(minutes=30))

    raw_token = recovery.token
    assert raw_token is not None

    async with session_factory() as session:
        row = (
            await session.execute(select(recovery_tokens).where(recovery_tokens.c.user_id == user.id))
        ).first()
        assert row is not None
        assert row.token_hash == hash_token(raw_token)
        assert row.used_at is None
        assert row.invalidated_at is None
        # The persisted record must not contain the raw usable token.
        assert raw_token not in row.token_hash
        assert raw_token != row.token_hash
        assert raw_token not in str(row._mapping)


@pytest.mark.asyncio
async def test_new_recovery_token_invalidates_prior_active_tokens(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        repo = DatabaseAuthRepository(session)
        await repo.create_user("Ivo", "ivo@example.com", "password123")
        first = await repo.create_recovery_token("ivo@example.com", ttl=timedelta(minutes=30))
        second = await repo.create_recovery_token("ivo@example.com", ttl=timedelta(minutes=30))

    # The first token should be invalidated; the second remains eligible.
    assert await _consume(session_factory, first.token) is False
    assert await _consume(session_factory, second.token) is True


async def _consume(session_factory, raw_token: str) -> bool:
    async with session_factory() as session:
        repo = DatabaseAuthRepository(session)
        return await repo.consume_recovery_token(raw_token, "newpassword123")


@pytest.mark.asyncio
async def test_token_is_consumed_exactly_once(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        repo = DatabaseAuthRepository(session)
        await repo.create_user("Nia", "nia@example.com", "password123")
        recovery = await repo.create_recovery_token("nia@example.com", ttl=timedelta(minutes=30))

    assert await _consume(session_factory, recovery.token) is True
    # Replay with the same token must fail without changing the password again.
    assert await _consume(session_factory, recovery.token) is False


@pytest.mark.asyncio
async def test_unknown_token_is_rejected_neutrally(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    assert await _consume(session_factory, "g" * 32) is False


@pytest.mark.asyncio
async def test_expired_token_is_rejected(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        repo = DatabaseAuthRepository(session)
        # A negative TTL produces an already-expired token.
        await repo.create_user("Lea", "lea@example.com", "password123")
        recovery = await repo.create_recovery_token("lea@example.com", ttl=timedelta(seconds=-1))

    assert await _consume(session_factory, recovery.token) is False


@pytest.mark.asyncio
async def test_successful_reset_updates_password_and_revokes_sessions(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        repo = DatabaseAuthRepository(session)
        user = await repo.create_user("Rex", "rex@example.com", "password123")
        auth_session = await repo.create_session(
            user.id, idle_ttl=timedelta(minutes=30), absolute_ttl=timedelta(days=1)
        )
        recovery = await repo.create_recovery_token("rex@example.com", ttl=timedelta(minutes=30))

    assert await _consume(session_factory, recovery.token) is True

    async with session_factory() as session:
        user_row = (
            await session.execute(select(users).where(users.c.email == "rex@example.com"))
        ).first()
        assert verify_password("newpassword123", user_row.password_hash)
        assert not verify_password("password123", user_row.password_hash)

        session_row = (
            await session.execute(select(sessions).where(sessions.c.id == auth_session.id))
        ).first()
        assert session_row.invalidated_at is not None


@pytest.mark.asyncio
async def test_concurrent_replay_yields_at_most_one_success(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    # SQLite serializes writers; to exercise the conditional consume we issue
    # two sequential attempts after the first success and assert only one wins.
    async with session_factory() as session:
        repo = DatabaseAuthRepository(session)
        await repo.create_user("Mo", "mo@example.com", "password123")
        recovery = await repo.create_recovery_token("mo@example.com", ttl=timedelta(minutes=30))

    results = await asyncio_gather_two(recovery.token, session_factory)
    assert sum(results) == 1


def asyncio_gather_two(raw_token: str, session_factory):
    import asyncio

    async def attempt() -> bool:
        async with session_factory() as session:
            repo = DatabaseAuthRepository(session)
            return await repo.consume_recovery_token(raw_token, "anotherpassword123")

    return asyncio.gather(attempt(), attempt())


@pytest.mark.asyncio
async def test_recovery_records_exclude_raw_token(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        repo = DatabaseAuthRepository(session)
        await repo.create_user("Zia", "zia@example.com", "password123")
        recovery = await repo.create_recovery_token("zia@example.com", ttl=timedelta(minutes=30))

    async with session_factory() as session:
        rows = (await session.execute(select(recovery_tokens))).all()
        assert len(rows) == 1
        # No column value equals the raw token; only its hash is stored.
        raw_token = recovery.token
        assert raw_token is not None
        assert all(raw_token != value for row in rows for value in row._mapping.values())
