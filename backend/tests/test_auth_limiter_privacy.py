"""Privacy regression tests for the authentication limiter.

Proves that limiter state, HTTP responses, application logs, and metrics
contain no password, recovery token, email, raw account ID, raw source
address, or digest key.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Iterator

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.settings import get_settings
from app.limiter.policy import EndpointCategory, LimiterOutcome
from app.main import app
from app.observability.metrics import metrics_registry

HMAC_SECRET = "privacy-hmac-secret"
ASSERTION_SECRET = "privacy-assertion-secret"

PROFILES = {
    "registration": {"source": {"limit": 1, "window_seconds": 3600}, "account": None, "storage_failure_mode": "fail_closed"},
    "credential_verification": {"source": {"limit": 2, "window_seconds": 3600}, "account": {"limit": 2, "window_seconds": 3600}, "storage_failure_mode": "fail_closed"},
    "recovery_initiation": {"source": {"limit": 2, "window_seconds": 3600}, "account": {"limit": 2, "window_seconds": 3600}, "storage_failure_mode": "fail_closed"},
    "recovery_confirmation": {"source": {"limit": 2, "window_seconds": 3600}, "account": {"limit": 2, "window_seconds": 3600}, "storage_failure_mode": "fail_closed"},
    "authjs_post": {"source": {"limit": 2, "window_seconds": 3600}, "account": None, "storage_failure_mode": "fail_closed"},
}

SENTINEL_EMAIL = "privacy-sentinel@example.com"
SENTINEL_PASSWORD = "privacy-sentinel-password"
SENTINEL_SOURCE = "198.51.100.77"
SENTINEL_ACCOUNT_ID = "00000000-0000-4000-8000-00000000dead"


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


def _frontend_source_key(address: str) -> str:
    """The opaque source key the frontend boundary derives for an address."""
    return hmac.new(
        HMAC_SECRET.encode(),
        f"1\x00source\x00{address.strip().lower()}".encode(),
        hashlib.sha256,
    ).hexdigest()


def _source_digest(address: str) -> str:
    """The persisted source digest the backend derives from the source key."""
    return hmac.new(
        HMAC_SECRET.encode(),
        f"1\x00source\x00{_frontend_source_key(address)}".encode(),
        hashlib.sha256,
    ).hexdigest()


def _account_digest(identifier: str) -> str:
    """The persisted account digest the backend derives from an identifier."""
    return hmac.new(
        HMAC_SECRET.encode(),
        f"1\x00account\x00{identifier.strip().lower()}".encode(),
        hashlib.sha256,
    ).hexdigest()


SENSITIVE_TOKENS = [
    SENTINEL_EMAIL,
    SENTINEL_PASSWORD,
    SENTINEL_SOURCE,
    SENTINEL_ACCOUNT_ID,
    HMAC_SECRET,
    ASSERTION_SECRET,
]


def assert_no_sensitive(text: str) -> None:
    for token in SENSITIVE_TOKENS:
        assert token not in text, f"sensitive token leaked: {token}"


@pytest.mark.asyncio
async def test_limited_response_bodies_and_headers_leak_no_sensitive_values(
    caplog: pytest.LogCaptureFixture,
) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Exhaust registration limit from a sentinel source.
        first = await client.post(
            "/auth/register",
            headers=source_headers(SENTINEL_SOURCE),
            json={"name": "Tuli", "email": SENTINEL_EMAIL, "password": SENTINEL_PASSWORD},
        )
        assert first.status_code == 201
        limited = await client.post(
            "/auth/register",
            headers=source_headers(SENTINEL_SOURCE),
            json={"name": "Ada", "email": "other@example.com", "password": SENTINEL_PASSWORD},
        )
        assert limited.status_code == 429

        body = limited.text
        headers_text = json.dumps(dict(limited.headers))
        assert_no_sensitive(body)
        assert_no_sensitive(headers_text)

        # Recovery limited responses keep the neutral contract with no account signal.
        recovery = await client.post(
            "/auth/recovery/request",
            headers=source_headers(SENTINEL_SOURCE),
            json={"email": SENTINEL_EMAIL},
        )
        assert_no_sensitive(recovery.text)


@pytest.mark.asyncio
async def test_limiter_metric_labels_are_closed_and_leak_no_identifiers() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            "/auth/register",
            headers=source_headers(SENTINEL_SOURCE),
            json={"name": "Tuli", "email": SENTINEL_EMAIL, "password": SENTINEL_PASSWORD},
        )
        await client.post(
            "/auth/register",
            headers=source_headers(SENTINEL_SOURCE),
            json={"name": "Ada", "email": "other@example.com", "password": SENTINEL_PASSWORD},
        )

    prometheus = metrics_registry.to_prometheus()
    assert "fotosintesis_limiter_outcomes_total" in prometheus
    assert_no_sensitive(prometheus)
    # Only closed category/outcome labels are permitted.
    for line in prometheus.splitlines():
        if not line.startswith("fotosintesis_limiter_outcomes_total"):
            continue
        assert 'category="' in line
        assert 'outcome="' in line
        assert SENTINEL_EMAIL not in line
        assert SENTINEL_SOURCE not in line


@pytest.mark.asyncio
async def test_application_logs_do_not_contain_sensitive_limiter_values(
    caplog: pytest.LogCaptureFixture,
) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            "/auth/register",
            headers=source_headers(SENTINEL_SOURCE),
            json={"name": "Tuli", "email": SENTINEL_EMAIL, "password": SENTINEL_PASSWORD},
        )
        await client.post(
            "/auth/credentials/verify",
            headers=source_headers(SENTINEL_SOURCE),
            json={"email": SENTINEL_EMAIL, "password": "wrong-" + SENTINEL_PASSWORD},
        )

    log_text = caplog.text
    assert_no_sensitive(log_text)


@pytest.mark.asyncio
async def test_recovery_confirmation_persists_no_raw_token_and_leaks_no_token(
    session_factory,
) -> None:
    from sqlalchemy import select

    from app.limiter.tables import limiter_state

    sentinel_token = "a" * 32
    sentinel_password = "sentinel-recovery-password"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/auth/recovery/confirm",
            headers=source_headers(SENTINEL_SOURCE),
            json={"token": sentinel_token, "password": sentinel_password},
        )
        assert response.status_code == 200
        assert sentinel_token not in response.text
        assert sentinel_password not in response.text

    async with session_factory() as session:
        rows = (await session.execute(select(limiter_state))).all()
        assert rows
        for row in rows:
            assert sentinel_token not in row.digest_key
            assert "a" * 32 not in row.digest_key
            assert sentinel_password not in row.digest_key


@pytest.mark.asyncio
async def test_actual_digests_are_persisted_but_never_exposed(
    session_factory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    from sqlalchemy import select

    from app.limiter.tables import limiter_state

    sentinel_token = "b" * 32
    sentinel_recovery_password = "sentinel-recovery-password"
    captured_surfaces: list[str] = []
    limiter_responses: list[str] = []

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Exercise registration, credentials, recovery initiation, and recovery
        # confirmation from the same sentinel source.
        register = await client.post(
            "/auth/register",
            headers=source_headers(SENTINEL_SOURCE),
            json={"name": "Tuli", "email": SENTINEL_EMAIL, "password": SENTINEL_PASSWORD},
        )
        captured_surfaces.append(register.text + json.dumps(dict(register.headers)))

        verify = await client.post(
            "/auth/credentials/verify",
            headers=source_headers(SENTINEL_SOURCE),
            json={"email": SENTINEL_EMAIL, "password": "wrong-" + SENTINEL_PASSWORD},
        )
        captured_surfaces.append(verify.text + json.dumps(dict(verify.headers)))

        recovery = await client.post(
            "/auth/recovery/request",
            headers=source_headers(SENTINEL_SOURCE),
            json={"email": SENTINEL_EMAIL},
        )
        captured_surfaces.append(recovery.text + json.dumps(dict(recovery.headers)))

        confirm = await client.post(
            "/auth/recovery/confirm",
            headers=source_headers(SENTINEL_SOURCE),
            json={"token": sentinel_token, "password": sentinel_recovery_password},
        )
        captured_surfaces.append(confirm.text + json.dumps(dict(confirm.headers)))

        # A limiter rejection response (registration source exhausted at 1)
        # must carry no raw value or digest.
        exhausted = await client.post(
            "/auth/register",
            headers=source_headers(SENTINEL_SOURCE),
            json={"name": "Ada", "email": "other@example.com", "password": SENTINEL_PASSWORD},
        )
        assert exhausted.status_code == 429
        limiter_responses.append(exhausted.text + json.dumps(dict(exhausted.headers)))

    source_key = _frontend_source_key(SENTINEL_SOURCE)
    source_digest = _source_digest(SENTINEL_SOURCE)
    account_digest = _account_digest(SENTINEL_EMAIL)
    token_digest = _account_digest(sentinel_token)

    # Opaque digest keys ARE the persisted limiter state (allowed in storage)…
    async with session_factory() as session:
        rows = (await session.execute(select(limiter_state))).all()
        stored = [row.digest_key for row in rows]
        assert source_digest in stored
        assert account_digest in stored
        assert token_digest in stored
        for row in rows:
            assert len(row.digest_key) == 64
            for raw in (
                SENTINEL_SOURCE,
                SENTINEL_EMAIL,
                sentinel_token,
                sentinel_recovery_password,
                SENTINEL_PASSWORD,
            ):
                assert raw not in row.digest_key

    # …but must NEVER appear on external or observability surfaces. Normal
    # auth responses legitimately echo the user's own email (e.g. the register
    # 201 body), so raw-value absence is asserted against the limiter
    # rejection surface plus logs and metrics, while digest absence is asserted
    # against every captured surface.
    surfaces = "\n".join(captured_surfaces)
    limiter_surface = "\n".join(limiter_responses)
    log_text = caplog.text
    prometheus = metrics_registry.to_prometheus()
    for digest in (source_key, source_digest, account_digest, token_digest):
        assert digest not in surfaces
        assert digest not in limiter_surface
        assert digest not in log_text
        assert digest not in prometheus
    for raw in (
        SENTINEL_SOURCE,
        SENTINEL_EMAIL,
        sentinel_token,
        sentinel_recovery_password,
        SENTINEL_PASSWORD,
    ):
        assert raw not in limiter_surface
        assert raw not in log_text
        assert raw not in prometheus


@pytest.mark.asyncio
async def test_limiter_metric_labels_are_exactly_category_and_outcome() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            "/auth/register",
            headers=source_headers(SENTINEL_SOURCE),
            json={"name": "Tuli", "email": SENTINEL_EMAIL, "password": SENTINEL_PASSWORD},
        )
        await client.post(
            "/auth/credentials/verify",
            headers=source_headers(SENTINEL_SOURCE),
            json={"email": SENTINEL_EMAIL, "password": "wrong-" + SENTINEL_PASSWORD},
        )
        await client.post(
            "/auth/recovery/request",
            headers=source_headers(SENTINEL_SOURCE),
            json={"email": SENTINEL_EMAIL},
        )
        await client.post(
            "/auth/recovery/confirm",
            headers=source_headers(SENTINEL_SOURCE),
            json={"token": "b" * 32, "password": "sentinel-recovery-password"},
        )

    prometheus = metrics_registry.to_prometheus()
    metric_lines = [
        line
        for line in prometheus.splitlines()
        if line.startswith("fotosintesis_limiter_outcomes_total{")
    ]
    assert metric_lines
    for line in metric_lines:
        label_text = line[line.index("{") + 1 : line.index("}")]
        pairs = dict(pair.split("=") for pair in label_text.split(","))
        # The exact closed label set is {category, outcome}; anything else
        # (account, source, digest, count, token) would be a leak.
        assert set(pairs.keys()) == {"category", "outcome"}
        for key, value in pairs.items():
            assert key in ("category", "outcome")
            assert value.strip('"') in {
                *[item.value for item in EndpointCategory],
                *[item.value for item in LimiterOutcome],
            }
