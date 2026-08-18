"""Honest storage-failure and lifecycle tests for the authentication limiter.

Proves that a limiter-storage exception never admits authentication work
(fail-closed only, no bounded fallback), an invalid production profile
prevents application startup, cleanup preserves rows inside the configured
retention period, and an active rejected window never returns a zero retry
delay (sub-second remaining windows round up).
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Iterator

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.settings import Settings, get_settings
from app.limiter.policy import (
    AdmissionOutcome,
    Dimension,
    EndpointCategory,
    EndpointPolicy,
    LimitProfile,
    LimiterPolicy,
    LimiterOutcome,
    StorageFailureMode,
)
from app.limiter.repository import LimiterRepository
from app.limiter.service import LimiterService
from app.limiter.tables import limiter_state


def _policy(retention_seconds: int = 3600, window_seconds: int = 3600) -> LimiterPolicy:
    return LimiterPolicy(
        endpoints={
            category: EndpointPolicy(
                source=LimitProfile(limit=5, window_seconds=window_seconds),
                account=(
                    LimitProfile(limit=5, window_seconds=window_seconds)
                    if category
                    in {
                        EndpointCategory.credential_verification,
                        EndpointCategory.recovery_initiation,
                        EndpointCategory.recovery_confirmation,
                    }
                    else None
                ),
                storage_failure_mode=StorageFailureMode.fail_closed,
            )
            for category in EndpointCategory
        },
        max_retry_after_seconds=3600,
        retention_seconds=retention_seconds,
    )


def _active_policy() -> LimiterPolicy:
    return _policy()


@contextmanager
def _enabled_env(monkeypatch: pytest.MonkeyPatch, profiles: dict) -> Iterator[None]:
    monkeypatch.setenv("AUTH_LIMITER_ENABLED", "true")
    monkeypatch.setenv("AUTH_LIMITER_HMAC_SECRET", "startup-hmac")
    monkeypatch.setenv("AUTH_LIMITER_ASSERTION_SECRET", "startup-assertion")
    monkeypatch.setenv("AUTH_LIMITER_PROFILES", json.dumps(profiles))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


ACCOUNT_SENSITIVE_CATEGORIES = (
    EndpointCategory.credential_verification,
    EndpointCategory.recovery_initiation,
    EndpointCategory.recovery_confirmation,
)


def _valid_profiles() -> dict:
    return {
        category.value: {
            "source": {"limit": 5, "window_seconds": 3600},
            "account": (
                {"limit": 5, "window_seconds": 3600}
                if category in ACCOUNT_SENSITIVE_CATEGORIES
                else None
            ),
            "storage_failure_mode": "fail_closed",
        }
        for category in EndpointCategory
    }


def test_production_with_limiter_disabled_fails_startup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("AUTH_LIMITER_ENABLED", "false")
    get_settings.cache_clear()
    from app.main import create_app

    with pytest.raises(ValueError, match="auth_limiter_enabled"):
        create_app()
    get_settings.cache_clear()


def test_production_with_missing_limiter_secrets_fails_startup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("AUTH_LIMITER_ENABLED", "true")
    monkeypatch.setenv("AUTH_LIMITER_PROFILES", json.dumps(_valid_profiles()))
    monkeypatch.delenv("AUTH_LIMITER_HMAC_SECRET", raising=False)
    monkeypatch.delenv("AUTH_LIMITER_ASSERTION_SECRET", raising=False)
    get_settings.cache_clear()
    from app.main import create_app

    with pytest.raises(ValueError, match="auth_limiter_hmac_secret|auth_limiter_assertion_secret"):
        create_app()
    get_settings.cache_clear()


@pytest.mark.parametrize("environment", ["local", "dev"])
def test_dev_and_local_may_start_with_the_limiter_disabled(
    monkeypatch: pytest.MonkeyPatch, environment: str
) -> None:
    monkeypatch.setenv("APP_ENV", environment)
    monkeypatch.setenv("AUTH_LIMITER_ENABLED", "false")
    get_settings.cache_clear()
    from app.main import create_app

    create_app()
    get_settings.cache_clear()


@pytest.mark.parametrize("category", [item.value for item in ACCOUNT_SENSITIVE_CATEGORIES])
def test_account_sensitive_category_with_null_account_fails_startup(
    monkeypatch: pytest.MonkeyPatch, category: str
) -> None:
    profiles = _valid_profiles()
    profiles[category]["account"] = None
    with _enabled_env(monkeypatch, profiles):
        from app.main import create_app

        with pytest.raises(ValueError, match="account"):
            create_app()


@pytest.mark.parametrize("category", ["registration", "authjs_post"])
def test_source_only_categories_accept_null_account_profiles(
    monkeypatch: pytest.MonkeyPatch, category: str
) -> None:
    profiles = _valid_profiles()
    assert profiles[category]["account"] is None
    with _enabled_env(monkeypatch, profiles):
        from app.main import create_app

        create_app()


def test_max_retry_after_zero_fails_settings_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUTH_LIMITER_MAX_RETRY_AFTER_SECONDS", "0")
    get_settings.cache_clear()
    with pytest.raises(ValidationError):
        Settings()
    get_settings.cache_clear()


def test_max_retry_after_one_succeeds_settings_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUTH_LIMITER_MAX_RETRY_AFTER_SECONDS", "1")
    get_settings.cache_clear()
    settings = Settings()
    assert settings.auth_limiter_max_retry_after_seconds == 1
    assert settings.limiter_policy().max_retry_after_seconds == 1
    get_settings.cache_clear()


def test_raise_storage_failure_uses_the_outcome_retry_delay() -> None:
    from app.limiter.http import raise_storage_failure

    outcome = AdmissionOutcome(
        outcome=LimiterOutcome.rejected,
        retry_after_seconds=5,
        storage_failure=True,
    )
    exc = raise_storage_failure(outcome)
    assert exc.status_code == 503
    assert exc.headers["Retry-After"] == "5"
    assert exc.detail == "Temporarily unavailable"


def test_raise_storage_failure_bounds_below_policy_maximum_never_zero() -> None:
    from app.limiter.http import raise_storage_failure

    # A storage failure for a category whose bounded retry resolves below the
    # old hard-coded 60 must carry that bounded value, never 0.
    outcome = AdmissionOutcome(
        outcome=LimiterOutcome.rejected,
        retry_after_seconds=1,
        storage_failure=True,
    )
    exc = raise_storage_failure(outcome)
    assert exc.headers["Retry-After"] == "1"


def test_raise_storage_failure_preserves_the_neutral_recovery_body() -> None:
    from app.limiter.http import (
        RECOVERY_NEUTRAL_MESSAGE,
        raise_storage_failure,
    )

    outcome = AdmissionOutcome(
        outcome=LimiterOutcome.rejected,
        retry_after_seconds=7,
        storage_failure=True,
    )
    exc = raise_storage_failure(outcome, is_recovery=True)
    assert exc.status_code == 503
    assert exc.detail == RECOVERY_NEUTRAL_MESSAGE
    assert exc.headers["Retry-After"] == "7"


def test_storage_failure_mode_supports_only_fail_closed() -> None:
    assert {mode.value for mode in StorageFailureMode} == {"fail_closed"}


@pytest.mark.asyncio
async def test_storage_exception_never_admits_authentication_work(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    policy = _active_policy()

    async def failing_admit(self, **kwargs):
        raise RuntimeError("simulated shared limiter storage failure")

    monkeypatch.setattr(
        "app.limiter.repository.LimiterRepository.admit",
        failing_admit,
    )

    async with session_factory() as session:
        service = LimiterService(
            repository=LimiterRepository(session),
            policy=policy,
            digest=__import__(
                "app.limiter.hashing", fromlist=["KeyedDigest"]
            ).KeyedDigest(secret="test-hmac", key_version=1),
            enabled=True,
        )
        outcome = await service.admit(
            category=EndpointCategory.registration,
            source_identifier="source-identifier",
        )
    assert outcome.outcome is LimiterOutcome.rejected
    assert outcome.storage_failure is True
    assert outcome.retry_after_seconds >= 1


def test_invalid_production_profile_prevents_startup(monkeypatch: pytest.MonkeyPatch) -> None:
    # Missing endpoint category coverage must fail at startup.
    with _enabled_env(
        monkeypatch,
        {
            "registration": {
                "source": {"limit": 10, "window_seconds": 3600},
                "storage_failure_mode": "fail_closed",
            }
        },
    ):
        from app.main import create_app

        with pytest.raises(ValueError, match="missing endpoint categories"):
            create_app()


def test_unknown_storage_failure_mode_prevents_startup(monkeypatch: pytest.MonkeyPatch) -> None:
    profiles = {
        category.value: {
            "source": {"limit": 5, "window_seconds": 3600},
            "account": None,
            "storage_failure_mode": "bounded_fallback",
        }
        for category in EndpointCategory
    }
    with _enabled_env(monkeypatch, profiles):
        from app.main import create_app

        with pytest.raises(ValueError, match="unknown storage_failure_mode"):
            create_app()


@pytest.mark.asyncio
async def test_cleanup_preserves_rows_inside_retention(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    retention = 3600
    window_seconds = 60
    policy = _policy(retention_seconds=retention, window_seconds=window_seconds)
    now = datetime.now(timezone.utc)

    async with session_factory() as session:
        repo = LimiterRepository(session)
        # A row whose window fully ended 30 minutes ago is still inside
        # retention (3600s) and must be preserved.
        await repo.admit(
            category=EndpointCategory.registration,
            keys={Dimension.source: "inside-retention"},
            policy=policy,
            now=now - timedelta(seconds=30 * 60),
        )
        # A row whose window fully ended 2 hours ago is beyond the retention
        # cutoff and must be removed.
        await repo.admit(
            category=EndpointCategory.registration,
            keys={Dimension.source: "beyond-retention"},
            policy=policy,
            now=now - timedelta(hours=2),
        )

    async with session_factory() as session:
        repo = LimiterRepository(session)
        removed = await repo.cleanup(
            batch_size=10, retention_seconds=retention, now=now
        )
    assert removed == 1

    async with session_factory() as session:
        remaining_keys = set(
            (
                await session.execute(
                    select(limiter_state.c.digest_key).where(
                        limiter_state.c.dimension == Dimension.source.value
                    )
                )
            ).scalars()
        )
    assert "inside-retention" in remaining_keys
    assert "beyond-retention" not in remaining_keys


@pytest.mark.asyncio
async def test_cleanup_removes_everything_at_the_retention_cutoff(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    retention = 60
    window_seconds = 60
    policy = _policy(retention_seconds=retention, window_seconds=window_seconds)
    now = datetime.now(timezone.utc)

    async with session_factory() as session:
        repo = LimiterRepository(session)
        # Seed far enough in the past that the fixed window has fully ended and
        # its window_end is older than the retention cutoff.
        await repo.admit(
            category=EndpointCategory.registration,
            keys={Dimension.source: "cutoff-row"},
            policy=policy,
            now=now - timedelta(seconds=retention + window_seconds + 1),
        )

    async with session_factory() as session:
        repo = LimiterRepository(session)
        removed = await repo.cleanup(batch_size=10, retention_seconds=retention, now=now)
    assert removed == 1


@pytest.mark.asyncio
async def test_active_rejection_never_returns_zero_retry(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    # A fixed window with a sub-second remainder must still return Retry-After
    # >= 1 so the client does not immediately retry inside an active rejection.
    policy = LimiterPolicy(
        endpoints={
            category: EndpointPolicy(
                source=LimitProfile(limit=1, window_seconds=5),
                account=None,
            )
            for category in EndpointCategory
        },
        max_retry_after_seconds=3600,
    )
    base = datetime.now(timezone.utc)
    window_start = (int(base.timestamp()) // 5) * 5
    # Deterministic: reject 100ms before the window ends (4.9s into a 5s window).
    within_window = datetime.fromtimestamp(window_start + 4, tz=timezone.utc)

    async with session_factory() as session:
        repo = LimiterRepository(session)
        first = await repo.admit(
            category=EndpointCategory.registration,
            keys={Dimension.source: "subsecond-source"},
            policy=policy,
            now=within_window,
        )
        assert first.outcome is LimiterOutcome.allowed

        rejected = await repo.admit(
            category=EndpointCategory.registration,
            keys={Dimension.source: "subsecond-source"},
            policy=policy,
            now=within_window + timedelta(milliseconds=900),
        )
    assert rejected.outcome is LimiterOutcome.rejected
    assert rejected.retry_after_seconds >= 1


@pytest.mark.asyncio
async def test_retry_delay_rounds_up_from_a_partial_window(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    # Exhaust a 5-second window, then reject 0.1s before it ends: the client
    # must receive a whole-second delay (1s), never 0.
    policy = LimiterPolicy(
        endpoints={
            category: EndpointPolicy(
                source=LimitProfile(limit=1, window_seconds=5),
                account=None,
            )
            for category in EndpointCategory
        },
        max_retry_after_seconds=3600,
    )
    base = datetime.now(timezone.utc)
    # Align to the fixed window boundary to control the remainder deterministically.
    window_start = (int(base.timestamp()) // 5) * 5
    window_now = datetime.fromtimestamp(window_start + 4, tz=timezone.utc)

    async with session_factory() as session:
        repo = LimiterRepository(session)
        await repo.admit(
            category=EndpointCategory.registration,
            keys={Dimension.source: "rounding-source"},
            policy=policy,
            now=window_now,
        )
        rejected = await repo.admit(
            category=EndpointCategory.registration,
            keys={Dimension.source: "rounding-source"},
            policy=policy,
            now=window_now + timedelta(milliseconds=900),
        )
    assert rejected.outcome is LimiterOutcome.rejected
    assert rejected.retry_after_seconds == 1
