"""
PostgreSQL integration test infrastructure.

Each test function gets a fresh engine and a unique schema with all
tables created from the SQLAlchemy metadata. After the test the schema
is dropped with CASCADE so multiple tests can run in parallel without
colliding on shared state.
"""

import os
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

BASE_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://fotosintesis:fotosintesis@localhost:5432/fotosintesis",
)


def pg_available() -> bool:
    return os.environ.get("SKIP_PG_TESTS", "").lower() not in ("1", "true", "yes")


def _create_schema_engine(database_url: str, schema: str) -> AsyncEngine:
    """Create an engine whose connections always operate on ``schema``.

    The asyncpg adapter runs ``SET search_path`` for every checkout
    via the ``server_settings`` connection argument.
    """
    return create_async_engine(
        database_url,
        pool_pre_ping=False,
        connect_args={"server_settings": {"search_path": f"{schema},public"}},
    )


@pytest.fixture
async def pg_schema() -> AsyncIterator[str]:
    """Yield a freshly created unique schema name and drop it after the test."""
    if not pg_available():
        pytest.skip("PostgreSQL integration tests disabled (SKIP_PG_TESTS is set)")

    schema = f"integration_{uuid4().hex}"
    bootstrap_engine = create_async_engine(BASE_DATABASE_URL, pool_pre_ping=False)
    try:
        async with bootstrap_engine.begin() as conn:
            await conn.execute(text(f'CREATE SCHEMA "{schema}"'))
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    finally:
        await bootstrap_engine.dispose()

    yield schema

    cleanup_engine = create_async_engine(BASE_DATABASE_URL, pool_pre_ping=False)
    try:
        async with cleanup_engine.begin() as conn:
            await conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
    finally:
        await cleanup_engine.dispose()


@pytest.fixture
async def pg_engine(pg_schema: str) -> AsyncIterator[AsyncEngine]:
    """Create an engine bound to the per-test schema and load all tables."""
    engine = _create_schema_engine(BASE_DATABASE_URL, pg_schema)

    from app.auth.tables import metadata

    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture
async def pg_session_factory(pg_engine) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    yield async_sessionmaker(pg_engine, expire_on_commit=False)


@pytest.fixture
async def test_user(pg_engine) -> UUID:
    user_id = uuid4()
    from app.auth.tables import users

    async with AsyncSession(pg_engine) as s:
        await s.execute(
            users.insert().values(
                id=user_id,
                name="Test User",
                email=f"{user_id}@test.invalid",
                email_verified=True,
            )
        )
        await s.commit()
    return user_id


@pytest.fixture
async def test_job(
    pg_session_factory,
    test_user: UUID,
) -> dict[str, Any]:
    from app.jobs.repository import JobRepository

    async with pg_session_factory() as s:
        repo = JobRepository(s)
        job_id = await repo.enqueue(
            job_type="ingest_validated_claims",
            payload_version=1,
            payload={"test": True},
            idempotency_key=f"fixture-job-{uuid4()}",
            user_id=test_user,
        )
        await s.commit()
        return {
            "id": job_id,
            "user_id": test_user,
            "job_type": "ingest_validated_claims",
        }
