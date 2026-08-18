"""Backend authentication limiter enforcement tests.

These tests enable the distributed limiter against the SQLite test database
and verify: every covered endpoint rejects at its bound before expensive or
state-changing work, bounded retry metadata is returned, successful login
relaxes only the account-specific credential counter, recovery responses
remain equivalent for known and unknown accounts, and storage failures fail
closed without exposing account or storage details.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone
from typing import Iterator
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.tables import recovery_tokens, users
from app.core.settings import get_settings
from app.limiter.tables import limiter_state
from app.main import app

HMAC_SECRET = "test-hmac-secret"
ASSERTION_SECRET = "test-assertion-secret"

PROFILES = {
    "registration": {"source": {"limit": 2, "window_seconds": 3600}, "account": None, "storage_failure_mode": "fail_closed"},
    "credential_verification": {
        "source": {"limit": 5, "window_seconds": 3600},
        "account": {"limit": 2, "window_seconds": 3600},
        "storage_failure_mode": "fail_closed",
    },
    "recovery_initiation": {
        "source": {"limit": 2, "window_seconds": 3600},
        "account": {"limit": 2, "window_seconds": 3600},
        "storage_failure_mode": "fail_closed",
    },
    "recovery_confirmation": {"source": {"limit": 2, "window_seconds": 3600}, "account": {"limit": 2, "window_seconds": 3600}, "storage_failure_mode": "fail_closed"},
    "authjs_post": {"source": {"limit": 5, "window_seconds": 3600}, "account": None, "storage_failure_mode": "fail_closed"},
}


@pytest.fixture(autouse=True)
def enable_limiter(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("AUTH_LIMITER_ENABLED", "true")
    monkeypatch.setenv("AUTH_LIMITER_HMAC_SECRET", HMAC_SECRET)
    monkeypatch.setenv("AUTH_LIMITER_ASSERTION_SECRET", ASSERTION_SECRET)
    monkeypatch.setenv("AUTH_LIMITER_HMAC_KEY_VERSION", "1")
    monkeypatch.setenv("AUTH_LIMITER_MAX_RETRY_AFTER_SECONDS", "3600")
    monkeypatch.setenv("AUTH_LIMITER_RETENTION_SECONDS", "86400")
    monkeypatch.setenv("AUTH_LIMITER_PROFILES", json.dumps(PROFILES))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def source_headers(address: str) -> dict[str, str]:
    """Build trusted source headers the way the frontend boundary does."""
    source_key = hmac.new(
        HMAC_SECRET.encode(),
        "1\x00source\x00".encode() + address.strip().lower().encode(),
        hashlib.sha256,
    ).hexdigest()
    assertion = hmac.new(ASSERTION_SECRET.encode(), source_key.encode(), hashlib.sha256).hexdigest()
    return {
        "x-fotosintesis-source-key": source_key,
        "x-fotosintesis-source-assertion": assertion,
    }


def spoofed_source_headers() -> dict[str, str]:
    """A source key presented without a valid internal assertion."""
    return {
        "x-fotosintesis-source-key": "a" * 64,
        "x-fotosintesis-source-assertion": "b" * 64,
    }


def no_source_headers() -> dict[str, str]:
    return {}


async def _limiter_rows(session_factory) -> list:
    async with session_factory() as session:
        return (await session.execute(select(limiter_state))).all()


@pytest.mark.asyncio
async def test_registration_is_rejected_before_password_hashing_at_the_source_bound(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for index in range(2):
            response = await client.post(
                "/auth/register",
                headers=source_headers("198.51.100.1"),
                json={"name": f"Tuli{index}", "email": f"tuli{index}@example.com", "password": "password123"},
            )
            assert response.status_code == 201

        limited = await client.post(
            "/auth/register",
            headers=source_headers("198.51.100.1"),
            json={"name": "Tuli", "email": "tuli@example.com", "password": "password123"},
        )
        assert limited.status_code == 429
        retry_after = int(limited.headers["retry-after"])
        assert 1 <= retry_after <= 3600

    async with session_factory() as session:
        rows = (await session.execute(select(users).where(users.c.email.like("tuli%@example.com")))).all()
        assert len(rows) == 2  # the two below-limit attempts created users; the limited one did not


@pytest.mark.asyncio
async def test_registration_from_a_different_source_is_admitted() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            "/auth/register",
            headers=source_headers("198.51.100.1"),
            json={"name": "Tuli", "email": "tuli@example.com", "password": "password123"},
        )
        await client.post(
            "/auth/register",
            headers=source_headers("198.51.100.1"),
            json={"name": "Ada", "email": "ada@example.com", "password": "password123"},
        )
        # A new source is not bound by the exhausted source window.
        fresh = await client.post(
            "/auth/register",
            headers=source_headers("203.0.113.5"),
            json={"name": "Lin", "email": "lin@example.com", "password": "password123"},
        )
        assert fresh.status_code == 201


@pytest.mark.asyncio
async def test_credential_verification_enforces_source_and_account_rules() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            "/auth/register",
            headers=source_headers("198.51.100.2"),
            json={"name": "Tuli", "email": "tuli@example.com", "password": "password123"},
        )
        payload = {"email": "tuli@example.com", "password": "wrong-password"}
        # Account limit is 2 per window for this account.
        first = await client.post("/auth/credentials/verify", headers=source_headers("198.51.100.2"), json=payload)
        assert first.status_code == 401
        second = await client.post("/auth/credentials/verify", headers=source_headers("198.51.100.2"), json=payload)
        assert second.status_code == 401
        third = await client.post("/auth/credentials/verify", headers=source_headers("198.51.100.2"), json=payload)
        assert third.status_code == 429
        assert "retry-after" in third.headers


@pytest.mark.asyncio
async def test_successful_login_relaxes_only_the_account_specific_counter(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            "/auth/register",
            headers=source_headers("198.51.100.3"),
            json={"name": "Tuli", "email": "tuli@example.com", "password": "password123"},
        )
        wrong = {"email": "tuli@example.com", "password": "wrong-password"}
        # One failed attempt consumes the account counter (account limit 2).
        failed = await client.post("/auth/credentials/verify", headers=source_headers("198.51.100.3"), json=wrong)
        assert failed.status_code == 401

        # A successful login is admitted and relaxes the account counter.
        ok = await client.post(
            "/auth/credentials/verify",
            headers=source_headers("198.51.100.3"),
            json={"email": "tuli@example.com", "password": "password123"},
        )
        assert ok.status_code == 200

        # The account counter was relaxed: two more failed attempts are still
        # admitted against the account rule (limit 2) before it is exhausted.
        second = await client.post("/auth/credentials/verify", headers=source_headers("198.51.100.3"), json=wrong)
        assert second.status_code == 401
        third = await client.post("/auth/credentials/verify", headers=source_headers("198.51.100.3"), json=wrong)
        assert third.status_code == 401
        # The account counter is now exhausted (2 failed attempts since the
        # successful login relaxed it).
        exhausted = await client.post("/auth/credentials/verify", headers=source_headers("198.51.100.3"), json=wrong)
        assert exhausted.status_code == 429

    async with session_factory() as session:
        rows = (await session.execute(select(limiter_state))).all()
        account_rows = [row for row in rows if row.dimension == "account"]
        assert account_rows, "expected account-scoped limiter state"
        # Only the credential_verification account counter is present.
        assert all(row.category == "credential_verification" for row in account_rows)


@pytest.mark.asyncio
async def test_recovery_initiation_limits_preserve_neutral_known_and_unknown_equivalence(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            "/auth/register",
            headers=source_headers("198.51.100.4"),
            json={"name": "Lin", "email": "lin@example.com", "password": "password123"},
        )
        known = await client.post(
            "/auth/recovery/request",
            headers=source_headers("198.51.100.4"),
            json={"email": "lin@example.com"},
        )
        missing = await client.post(
            "/auth/recovery/request",
            headers=source_headers("198.51.100.4"),
            json={"email": "missing@example.com"},
        )
        assert known.status_code == 200
        assert missing.status_code == 200
        assert known.json() == missing.json()

        # Source bound (2) exhausted; both known and unknown are rejected with
        # the same neutral body and equivalent retry contract.
        limited_known = await client.post(
            "/auth/recovery/request",
            headers=source_headers("198.51.100.4"),
            json={"email": "lin@example.com"},
        )
        limited_missing = await client.post(
            "/auth/recovery/request",
            headers=source_headers("198.51.100.4"),
            json={"email": "missing@example.com"},
        )
        assert limited_known.status_code == 429
        assert limited_missing.status_code == 429
        assert limited_known.json() == limited_missing.json()
        assert limited_known.json()["detail"] == limited_missing.json()["detail"]
        assert limited_known.headers["retry-after"] == limited_missing.headers["retry-after"]

    async with session_factory() as session:
        rows = (await session.execute(select(recovery_tokens))).all()
        # Only the two below-limit requests created tokens.
        assert len(rows) == 2


@pytest.mark.asyncio
async def test_recovery_confirmation_applies_its_source_policy() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        payload = {"token": "a" * 32, "password": "password123"}
        first = await client.post("/auth/recovery/confirm", headers=source_headers("198.51.100.6"), json=payload)
        assert first.status_code == 200
        second = await client.post("/auth/recovery/confirm", headers=source_headers("198.51.100.6"), json=payload)
        assert second.status_code == 200
        limited = await client.post("/auth/recovery/confirm", headers=source_headers("198.51.100.6"), json=payload)
        assert limited.status_code == 429
        assert "retry-after" in limited.headers


@pytest.mark.asyncio
async def test_recovery_confirmation_token_account_bound_cannot_be_bypassed_by_source_rotation(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    # The account dimension is derived from the submitted token. Rotating the
    # source address must not bypass the token-specific confirmation bound.
    token = "a" * 32
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        payload = {"token": token, "password": "password123"}
        for index in range(2):
            response = await client.post(
                "/auth/recovery/confirm",
                headers=source_headers(f"198.51.100.{70 + index}"),
                json=payload,
            )
            assert response.status_code == 200

        # A third confirmation for the same token from a fresh source is still
        # rejected by the token-bound account rule.
        exhausted = await client.post(
            "/auth/recovery/confirm",
            headers=source_headers("198.51.100.90"),
            json=payload,
        )
        assert exhausted.status_code == 429

    async with session_factory() as session:
        rows = (await session.execute(select(limiter_state))).all()
        account_rows = [row for row in rows if row.dimension == "account"]
        assert account_rows
        assert all(row.category == "recovery_confirmation" for row in account_rows)
        # No raw token is persisted anywhere in limiter state.
        for row in rows:
            assert "a" * 32 not in row.digest_key
            assert token not in row.digest_key


@pytest.mark.asyncio
async def test_recovery_confirmation_different_tokens_are_independent_account_keys() -> None:
    # Exhaust token A's account rule; a different token from a fresh source is
    # unaffected, and token A remains bound even from another fresh source.
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        first_token = {"token": "a" * 32, "password": "password123"}
        second_token = {"token": "b" * 32, "password": "password123"}
        for _ in range(2):
            await client.post(
                "/auth/recovery/confirm",
                headers=source_headers("198.51.100.91"),
                json=first_token,
            )
        # A different token from a fresh source is admitted.
        fresh = await client.post(
            "/auth/recovery/confirm",
            headers=source_headers("198.51.100.95"),
            json=second_token,
        )
        assert fresh.status_code == 200
        # The exhausted token remains bound even from yet another fresh source:
        # rotating the source cannot bypass the token-specific account rule.
        exhausted = await client.post(
            "/auth/recovery/confirm",
            headers=source_headers("198.51.100.96"),
            json=first_token,
        )
        assert exhausted.status_code == 429


@pytest.mark.asyncio
async def test_recovery_confirmation_is_neutral_across_token_states() -> None:
    # Token-shaped requests that reach token-state handling expose no
    # distinction between known, unknown, and exhausted tokens. Schema-invalid
    # payloads are a deterministic 422 validation error (see the separate
    # malformed-payload test), so malformed input never claims a recovery
    # status.
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Exhaust token A's account rule from fresh sources so only the account
        # dimension binds.
        token = "c" * 32
        for index in range(2):
            ok = await client.post(
                "/auth/recovery/confirm",
                headers=source_headers(f"198.51.100.{100 + index}"),
                json={"token": token, "password": "password123"},
            )
            assert ok.status_code == 200
        # A different token from a fresh source is neutral and admitted.
        other = await client.post(
            "/auth/recovery/confirm",
            headers=source_headers("198.51.100.110"),
            json={"token": "d" * 32, "password": "password123"},
        )
        assert other.status_code == 200
        # The exhausted token now rejects with the neutral recovery body.
        exhausted = await client.post(
            "/auth/recovery/confirm",
            headers=source_headers("198.51.100.111"),
            json={"token": token, "password": "password123"},
        )
        assert exhausted.status_code == 429
        assert "If an account with that email exists" in exhausted.json()["detail"]


@pytest.mark.asyncio
async def test_recovery_confirmation_malformed_payload_is_a_deterministic_validation_error() -> None:
    # Schema-invalid recovery-confirmation payloads are rejected by FastAPI
    # body validation before any token-state handling: a generic 422 with no
    # recovery, token, account, or storage detail.
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        short = await client.post(
            "/auth/recovery/confirm",
            headers=source_headers("198.51.100.92"),
            json={"token": "short", "password": "password123"},
        )
        assert short.status_code == 422
        assert "If an account with that email exists" not in short.text
        assert "token" not in short.json()["detail"][0].get("msg", "").lower()

        missing_field = await client.post(
            "/auth/recovery/confirm",
            headers=source_headers("198.51.100.92"),
            json={"token": "a" * 32},
        )
        assert missing_field.status_code == 422


@pytest.mark.asyncio
async def test_recovery_confirmation_different_unknown_tokens_get_equivalent_behavior() -> None:
    # Two well-shaped unknown tokens from fresh sources receive the same
    # neutral prepared response: no distinction between unknown tokens.
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        first = await client.post(
            "/auth/recovery/confirm",
            headers=source_headers("198.51.100.113"),
            json={"token": "e" * 32, "password": "password123"},
        )
        second = await client.post(
            "/auth/recovery/confirm",
            headers=source_headers("198.51.100.114"),
            json={"token": "f" * 32, "password": "password123"},
        )
        assert first.status_code == 200
        assert second.status_code == 200
        assert first.json() == second.json()
        assert first.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_missing_or_spoofed_source_is_rejected_conservatively(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        payload = {"name": "Tuli", "email": "tuli@example.com", "password": "password123"}

        missing = await client.post("/auth/register", headers=no_source_headers(), json=payload)
        assert missing.status_code == 429

        spoofed = await client.post("/auth/register", headers=spoofed_source_headers(), json=payload)
        assert spoofed.status_code == 429

    async with session_factory() as session:
        row = (
            await session.execute(select(users).where(users.c.email == "tuli@example.com"))
        ).first()
        assert row is None


@pytest.mark.asyncio
async def test_limited_response_matches_the_documented_detail_and_retry_after_contract() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for _ in range(2):
            await client.post(
                "/auth/register",
                headers=source_headers("198.51.100.30"),
                json={"name": "Tuli", "email": "tuli@example.com", "password": "password123"},
            )
        limited = await client.post(
            "/auth/register",
            headers=source_headers("198.51.100.30"),
            json={"name": "Ada", "email": "ada@example.com", "password": "password123"},
        )
        assert limited.status_code == 429
        # The JSON body contains only the generic detail field; retry timing is
        # carried by the Retry-After response header declared in OpenAPI.
        assert set(limited.json().keys()) == {"detail"}
        assert "Retry-After" in limited.headers
        retry_after = int(limited.headers["Retry-After"])
        assert retry_after >= 1


@pytest.mark.asyncio
async def test_recovery_limited_body_and_retry_contract_remain_neutral() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for _ in range(2):
            await client.post(
                "/auth/recovery/request",
                headers=source_headers("198.51.100.31"),
                json={"email": "tuli@example.com"},
            )
        limited = await client.post(
            "/auth/recovery/request",
            headers=source_headers("198.51.100.31"),
            json={"email": "missing@example.com"},
        )
        assert limited.status_code == 429
        body = limited.json()
        assert set(body.keys()) == {"detail"}
        assert "If an account with that email exists" in body["detail"]
        assert "Retry-After" in limited.headers


@pytest.mark.asyncio
async def test_authjs_post_admission_endpoint_has_a_real_runtime_call_site() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        admitted = await client.post(
            "/auth/admit/authjs_post",
            headers=source_headers("198.51.100.20"),
        )
        assert admitted.status_code == 200
        assert admitted.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_repeated_relevant_authjs_posts_are_rejected_across_shared_state() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for _ in range(5):
            ok = await client.post(
                "/auth/admit/authjs_post",
                headers=source_headers("198.51.100.21"),
            )
            assert ok.status_code == 200

        limited = await client.post(
            "/auth/admit/authjs_post",
            headers=source_headers("198.51.100.21"),
        )
        assert limited.status_code == 429
        retry_after = int(limited.headers["retry-after"])
        assert 1 <= retry_after <= 3600
        assert "retry-after" in limited.headers


@pytest.mark.asyncio
async def test_authjs_post_missing_source_is_rejected_conservatively() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        missing = await client.post("/auth/admit/authjs_post", headers=no_source_headers())
        assert missing.status_code == 429
        spoofed = await client.post("/auth/admit/authjs_post", headers=spoofed_source_headers())
        assert spoofed.status_code == 429


@pytest.mark.asyncio
async def test_limiter_state_contains_only_opaque_keyed_digests(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            "/auth/register",
            headers=source_headers("198.51.100.9"),
            json={"name": "Tuli", "email": "tuli@example.com", "password": "password123"},
        )
        await client.post(
            "/auth/credentials/verify",
            headers=source_headers("198.51.100.9"),
            json={"email": "tuli@example.com", "password": "wrong-password"},
        )

    async with session_factory() as session:
        rows = (await session.execute(select(limiter_state))).all()
        assert rows
        for row in rows:
            assert len(row.digest_key) == 64
            assert "tuli" not in row.digest_key
            assert "198.51.100.9" not in row.digest_key
            assert row.category in {"registration", "credential_verification"}
            assert row.count >= 0


@pytest.mark.asyncio
async def test_storage_failure_respects_a_positive_policy_maximum(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A one-second configured maximum must produce Retry-After: 1 on a storage
    # failure, proving storage-failure timing follows the same authoritative
    # policy contract as 429 responses instead of a hard-coded 60.
    monkeypatch.setenv("AUTH_LIMITER_MAX_RETRY_AFTER_SECONDS", "1")
    get_settings.cache_clear()

    async def failing_admit(self, **kwargs):
        raise RuntimeError("simulated shared limiter storage failure")

    monkeypatch.setattr(
        "app.limiter.repository.LimiterRepository.admit",
        failing_admit,
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/auth/register",
            headers=source_headers("198.51.100.40"),
            json={"name": "Tuli", "email": "tuli@example.com", "password": "password123"},
        )
        assert response.status_code == 503
        assert set(response.json().keys()) == {"detail"}
        assert response.json()["detail"] == "Temporarily unavailable"
        assert int(response.headers["retry-after"]) == 1
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_storage_failure_maximum_below_60_bounds_the_retry_header(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUTH_LIMITER_MAX_RETRY_AFTER_SECONDS", "5")
    get_settings.cache_clear()

    async def failing_admit(self, **kwargs):
        raise RuntimeError("simulated shared limiter storage failure")

    monkeypatch.setattr(
        "app.limiter.repository.LimiterRepository.admit",
        failing_admit,
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/auth/register",
            headers=source_headers("198.51.100.41"),
            json={"name": "Tuli", "email": "tuli@example.com", "password": "password123"},
        )
        assert response.status_code == 503
        assert 1 <= int(response.headers["retry-after"]) <= 5
        assert int(response.headers["retry-after"]) != 60
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_recovery_storage_failure_preserves_the_neutral_body_and_bounded_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUTH_LIMITER_MAX_RETRY_AFTER_SECONDS", "3")
    get_settings.cache_clear()

    async def failing_admit(self, **kwargs):
        raise RuntimeError("simulated shared limiter storage failure")

    monkeypatch.setattr(
        "app.limiter.repository.LimiterRepository.admit",
        failing_admit,
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/auth/recovery/request",
            headers=source_headers("198.51.100.42"),
            json={"email": "tuli@example.com"},
        )
        assert response.status_code == 503
        assert "If an account with that email exists" in response.json()["detail"]
        assert 1 <= int(response.headers["retry-after"]) <= 3
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_no_limited_or_storage_failure_response_returns_zero_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Exhaust the registration source bound: every 429 must carry >= 1.
        for _ in range(2):
            await client.post(
                "/auth/register",
                headers=source_headers("198.51.100.43"),
                json={"name": "Tuli", "email": "tuli@example.com", "password": "password123"},
            )
        limited = await client.post(
            "/auth/register",
            headers=source_headers("198.51.100.43"),
            json={"name": "Ada", "email": "ada@example.com", "password": "password123"},
        )
        assert limited.status_code == 429
        assert int(limited.headers["retry-after"]) >= 1

    async def failing_admit(self, **kwargs):
        raise RuntimeError("simulated shared limiter storage failure")

    monkeypatch.setattr(
        "app.limiter.repository.LimiterRepository.admit",
        failing_admit,
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        failed = await client.post(
            "/auth/register",
            headers=source_headers("198.51.100.44"),
            json={"name": "Tuli", "email": "tuli@example.com", "password": "password123"},
        )
        assert failed.status_code == 503
        assert int(failed.headers["retry-after"]) >= 1


@pytest.mark.asyncio
async def test_backend_accepts_the_frontend_trusted_client_source_assertion(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    # Contract-level integration evidence: the backend admits a source key +
    # assertion derived exactly as the frontend trust boundary derives them for
    # the trusted client address (the first of the two platform-appended
    # entries). The attacker-prefix / load-balancer distinction is enforced at
    # the frontend boundary (see the register route tests and the Google
    # external Application Load Balancer forwarding contract); the backend only
    # requires a validly asserted opaque key and rejects a missing or invalid
    # assertion conservatively (covered by
    # test_missing_or_spoofed_source_is_rejected_conservatively). This is
    # contract-level integration coverage, not a live GKE deployment spoofing
    # test.
    trusted_client = "203.0.113.55"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        admitted = await client.post(
            "/auth/register",
            headers=source_headers(trusted_client),
            json={"name": "Tuli", "email": "tuli@example.com", "password": "password123"},
        )
        assert admitted.status_code == 201

    async with session_factory() as session:
        row = (await session.execute(select(users).where(users.c.email == "tuli@example.com"))).first()
        assert row is not None


@pytest.mark.asyncio
async def test_limiter_storage_failure_fails_closed_without_exposing_details(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def failing_admit(self, **kwargs):
        raise RuntimeError("simulated shared limiter storage failure")

    monkeypatch.setattr(
        "app.limiter.repository.LimiterRepository.admit",
        failing_admit,
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        register = await client.post(
            "/auth/register",
            headers=source_headers("198.51.100.10"),
            json={"name": "Tuli", "email": "tuli@example.com", "password": "password123"},
        )
        assert register.status_code == 503
        assert "storage" not in register.text.lower()
        assert "tuli@example.com" not in register.text

        verify = await client.post(
            "/auth/credentials/verify",
            headers=source_headers("198.51.100.10"),
            json={"email": "tuli@example.com", "password": "password123"},
        )
        assert verify.status_code == 503
        assert "storage" not in verify.text.lower()

        recovery = await client.post(
            "/auth/recovery/request",
            headers=source_headers("198.51.100.10"),
            json={"email": "tuli@example.com"},
        )
        assert recovery.status_code == 503
        assert "If an account with that email exists" in recovery.text

        confirm = await client.post(
            "/auth/recovery/confirm",
            headers=source_headers("198.51.100.10"),
            json={"token": "a" * 32, "password": "password123"},
        )
        assert confirm.status_code == 503

        authjs = await client.post(
            "/auth/admit/authjs_post",
            headers=source_headers("198.51.100.10"),
        )
        assert authjs.status_code == 503

    async with session_factory() as session:
        user_row = (
            await session.execute(select(users).where(users.c.email == "tuli@example.com"))
        ).first()
        recovery_rows = (await session.execute(select(recovery_tokens))).all()
        assert user_row is None
        assert not recovery_rows
