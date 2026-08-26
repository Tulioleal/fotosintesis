"""Deployment-level verification that two application instances share one limit.

This test proves the distributed enforcement contract without needing real
Kubernetes replicas: it runs two genuinely independent FastAPI application
objects (as separate pods would behave), each with its own engine/session
stack and instance-local dependency override, against the SAME isolated
PostgreSQL schema. Their combined invalid credential attempts cannot exceed
the configured shared account bound, and the test proves both application
stacks actually served requests.

It is skipped when PostgreSQL integration is disabled.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.settings import get_settings
from app.db.session import get_async_session
from app.limiter.tables import limiter_state
from app.main import create_app

SHARED_ACCOUNT_LIMIT = 3
SHARED_SOURCE_LIMIT = 10
HMAC_SECRET = "multireplica-hmac-secret"
ASSERTION_SECRET = "multireplica-assertion-secret"

PROFILES = {
    "registration": {"source": {"limit": SHARED_SOURCE_LIMIT, "window_seconds": 3600}, "account": None, "storage_failure_mode": "fail_closed"},
    "credential_verification": {
        "source": {"limit": SHARED_SOURCE_LIMIT, "window_seconds": 3600},
        "account": {"limit": SHARED_ACCOUNT_LIMIT, "window_seconds": 3600},
        "storage_failure_mode": "fail_closed",
    },
    "recovery_initiation": {
        "source": {"limit": SHARED_SOURCE_LIMIT, "window_seconds": 3600},
        "account": {"limit": 2, "window_seconds": 3600},
        "storage_failure_mode": "fail_closed",
    },
    "recovery_confirmation": {
        "source": {"limit": SHARED_SOURCE_LIMIT, "window_seconds": 3600},
        "account": {"limit": 2, "window_seconds": 3600},
        "storage_failure_mode": "fail_closed",
    },
    "authjs_post": {"source": {"limit": SHARED_SOURCE_LIMIT, "window_seconds": 3600}, "account": None, "storage_failure_mode": "fail_closed"},
}


def _second_engine(source_engine: AsyncEngine, schema: str) -> AsyncEngine:
    """A second independent engine bound to the same schema/database."""
    return create_async_engine(
        source_engine.url.render_as_string(hide_password=False),
        pool_pre_ping=True,
        connect_args={"server_settings": {"search_path": f"{schema},public"}},
    )


def _source_headers(secret: str, assertion: str, address: str) -> dict[str, str]:
    source_key = hmac.new(
        secret.encode(),
        "1\x00source\x00".encode() + address.strip().lower().encode(),
        hashlib.sha256,
    ).hexdigest()
    assertion_value = hmac.new(
        assertion.encode(), source_key.encode(), hashlib.sha256
    ).hexdigest()
    return {
        "x-fotosintesis-source-key": source_key,
        "x-fotosintesis-source-assertion": assertion_value,
    }


def _account_digest(email: str) -> str:
    return hmac.new(
        HMAC_SECRET.encode(),
        "1\x00account\x00".encode() + email.strip().lower().encode(),
        hashlib.sha256,
    ).hexdigest()


def _derived_source_digest(source_key_header: str) -> str:
    # The backend derives the persisted source digest from the opaque source
    # key header produced by the frontend trust boundary (a second derivation
    # over the raw address), so the stored row must match that value.
    return hmac.new(
        HMAC_SECRET.encode(),
        "1\x00source\x00".encode() + source_key_header.strip().lower().encode(),
        hashlib.sha256,
    ).hexdigest()


async def test_two_http_instances_share_one_account_credential_bound(
    pg_engine: AsyncEngine,
    pg_schema: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUTH_LIMITER_ENABLED", "true")
    monkeypatch.setenv("AUTH_LIMITER_HMAC_SECRET", HMAC_SECRET)
    monkeypatch.setenv("AUTH_LIMITER_ASSERTION_SECRET", ASSERTION_SECRET)
    monkeypatch.setenv("AUTH_LIMITER_HMAC_KEY_VERSION", "1")
    monkeypatch.setenv("AUTH_LIMITER_PROFILES", json.dumps(PROFILES))
    get_settings.cache_clear()

    # Two genuinely independent application objects, each with its own
    # engine/session stack bound to the same isolated schema.
    app_a = create_app()
    app_b = create_app()
    assert app_a is not app_b

    sessions_a = async_sessionmaker(pg_engine, expire_on_commit=False)
    engine_b = _second_engine(pg_engine, pg_schema)
    sessions_b = async_sessionmaker(engine_b, expire_on_commit=False)

    override_calls = {"a": 0, "b": 0}

    def _override_for(
        sessions: async_sessionmaker[AsyncSession], key: str
    ) -> AsyncIterator[AsyncSession]:
        async def _override() -> AsyncIterator[AsyncSession]:
            override_calls[key] += 1
            async with sessions() as session:
                yield session

        return _override

    # Instance-local dependency overrides: each application resolves its own
    # session stack, proving the shared bound is not an artifact of one global
    # application override.
    app_a.dependency_overrides[get_async_session] = _override_for(sessions_a, "a")
    app_b.dependency_overrides[get_async_session] = _override_for(sessions_b, "b")

    account_email = f"{uuid4().hex}@example.com"
    source_ip_a = "198.51.100.40"
    source_ip_b = "198.51.100.41"
    headers_a = _source_headers(HMAC_SECRET, ASSERTION_SECRET, source_ip_a)
    headers_b = _source_headers(HMAC_SECRET, ASSERTION_SECRET, source_ip_b)
    source_key_a = headers_a["x-fotosintesis-source-key"]
    source_key_b = headers_b["x-fotosintesis-source-key"]

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app_a), base_url="http://test"
        ) as client_a:
            async with AsyncClient(
                transport=ASGITransport(app=app_b), base_url="http://test"
            ) as client_b:
                async def invalid_attempt(
                    client: AsyncClient, headers: dict[str, str]
                ) -> int:
                    response = await client.post(
                        "/auth/credentials/verify",
                        headers=headers,
                        json={"email": account_email, "password": "wrong-password"},
                    )
                    # 401 means admitted-but-invalid; 429 means rejected by the
                    # shared limiter. Anything else is a failure.
                    assert response.status_code in (401, 429)
                    return 1 if response.status_code == 401 else 0

                # Deterministic seed: each application instance admits one
                # attempt from its own source so both application stacks serve
                # requests and both source keys provably create source rows.
                assert await invalid_attempt(client_a, headers_a) == 1
                assert await invalid_attempt(client_b, headers_b) == 1

                results = await asyncio.gather(
                    *[invalid_attempt(client_a, headers_a) for _ in range(5)]
                    + [invalid_attempt(client_b, headers_b) for _ in range(5)]
                )
                # The shared account bound admitted exactly one more of the
                # concurrent attempts (reaching the 3-attempt limit) and
                # rejected the remaining nine across both instances.
                assert sum(results) == SHARED_ACCOUNT_LIMIT - 2
                combined_allowed = 2 + sum(results)
                assert combined_allowed == SHARED_ACCOUNT_LIMIT

        # Both application-local session stacks actually served requests.
        assert override_calls["a"] > 0
        assert override_calls["b"] > 0

        # Both engines run on the isolated per-test schema.
        async with AsyncSession(pg_engine) as session:
            schema_a = (
                await session.execute(text("SELECT current_schema()"))
            ).scalar_one()
        async with AsyncSession(engine_b) as session:
            schema_b = (
                await session.execute(text("SELECT current_schema()"))
            ).scalar_one()
        assert schema_a == pg_schema
        assert schema_b == pg_schema

        async with AsyncSession(pg_engine) as session:
            rows = (await session.execute(select(limiter_state))).all()
            # Both trusted sources created separate opaque source rows.
            source_keys = {
                row.digest_key for row in rows if row.dimension == "source"
            }
            assert source_keys == {
                _derived_source_digest(source_key_a),
                _derived_source_digest(source_key_b),
            }
            # Exactly one shared account counter enforced the combined bound.
            account_rows = [
                row for row in rows if row.dimension == "account"
            ]
            assert len(account_rows) == 1
            account_row = account_rows[0]
            assert account_row.digest_key == _account_digest(account_email)
            assert account_row.category == "credential_verification"
            assert account_row.count == SHARED_ACCOUNT_LIMIT
            for row in rows:
                # Opaque digests only; no raw account or source identifiers.
                assert account_email not in row.digest_key
                assert len(row.digest_key) == 64
    finally:
        app_a.dependency_overrides.clear()
        app_b.dependency_overrides.clear()
        get_settings.cache_clear()
        await engine_b.dispose()