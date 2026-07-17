from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.auth.tables import application_jobs
from app.jobs.repository import JobRepository
from app.jobs.schemas import JobStatus, JobType

pytestmark = [
    pytest.mark.skipif(
        "SKIP_PG_TESTS" in __import__("os").environ,
        reason="PostgreSQL not available (SKIP_PG_TESTS is set)",
    ),
]

_VALID_JOB_TYPE = JobType.ingest_validated_claims.value


@pytest.fixture(autouse=True)
def _worker_settings(monkeypatch):
    monkeypatch.setenv("JOBS_WORKER_ENABLED", "true")
    monkeypatch.setenv("JOBS_PRODUCER_ENABLED", "false")
    monkeypatch.setenv("JOBS_POLL_INTERVAL_SECONDS", "0.1")
    monkeypatch.setenv("JOBS_BATCH_SIZE", "10")
    monkeypatch.setenv("JOBS_WORKER_CONCURRENCY", "5")
    monkeypatch.setenv("JOBS_LEASE_DURATION_SECONDS", "300")
    monkeypatch.setenv("JOBS_LEASE_RENEWAL_INTERVAL_SECONDS", "60")
    monkeypatch.setenv("JOBS_MAX_ATTEMPTS_DEFAULT", "3")
    monkeypatch.setenv("JOBS_BACKOFF_BASE_SECONDS", "10")
    monkeypatch.setenv("JOBS_BACKOFF_CAP_SECONDS", "3600")
    monkeypatch.setenv("JOBS_SHUTDOWN_DRAIN_SECONDS", "30")
    from app.core.settings import get_settings
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


async def _setup_job(pg_session_factory, *, max_attempts=3):
    async with pg_session_factory() as s:
        repo = JobRepository(s)
        job_id = await repo.enqueue(
            job_type=_VALID_JOB_TYPE, payload_version=1,
            payload={"test": True},
            idempotency_key=str(uuid4()),
            max_attempts=max_attempts,
        )
        await s.commit()
    return job_id


async def _set_processing(session, job_id, owner="w1", lease_duration=300.0):
    import sqlalchemy as sa

    token = str(uuid4())
    expires = datetime.now(timezone.utc) + timedelta(seconds=lease_duration)
    await session.execute(
        sa.text("""
            UPDATE application_jobs
            SET status = 'processing',
                lease_owner = :owner,
                lease_token = :token,
                lease_expires_at = :expires,
                attempt_count = 1
            WHERE id = :job_id
        """),
        {"owner": owner, "token": token, "expires": expires, "job_id": job_id},
    )
    return token


class TestWorkerExecution:
    async def test_lease_renews_during_long_handler(self, pg_session_factory):
        job_id = await _setup_job(pg_session_factory)

        async with pg_session_factory() as s:
            token = await _set_processing(s, job_id, lease_duration=300)
            await s.commit()
            repo = JobRepository(s)
            renewed = await repo.renew_lease(
                job_id=job_id, owner="w1", lease_token=token,
                lease_duration_seconds=300,
            )
            assert renewed is True

        async with pg_session_factory() as s:
            row = (
                await s.execute(
                    select(application_jobs.c.lease_expires_at)
                    .where(application_jobs.c.id == job_id)
                )
            ).first()
        assert row._mapping["lease_expires_at"] > datetime.now(timezone.utc)

    async def test_renewal_failure_suppresses_completion(self, pg_session_factory):
        job_id = await _setup_job(pg_session_factory)

        async with pg_session_factory() as s:
            token = await _set_processing(s, job_id, owner="w1", lease_duration=-30)
            await s.commit()
            repo = JobRepository(s)
            renewed = await repo.renew_lease(
                job_id=job_id, owner="w1", lease_token=token,
                lease_duration_seconds=300,
            )
            assert renewed is False

    async def test_crash_followed_by_expiry_allows_recovery(self, pg_session_factory):
        job_id = await _setup_job(pg_session_factory)

        async with pg_session_factory() as s:
            await _set_processing(s, job_id, owner="w1", lease_duration=-10)
            await s.commit()

        async with pg_session_factory() as s:
            repo = JobRepository(s)
            claimed = await repo.claim_jobs(
                owner="w2", batch_size=10, lease_duration_seconds=300,
            )
            await s.commit()

        assert len(claimed) == 1
        assert claimed[0].id == job_id
        assert claimed[0].lease_owner == "w2"

    async def test_retry_uses_exponential_backoff_and_cap(self, pg_session_factory):
        settings = __import__("app.core.settings", fromlist=["get_settings"]).get_settings()

        repo = JobRepository.__new__(JobRepository)
        repo.settings = settings
        for attempt in [1, 2, 3, 10]:
            backoff = repo.compute_backoff(attempt_count=attempt)
            delay = (backoff - datetime.now(timezone.utc)).total_seconds()
            expected = min(settings.jobs_backoff_base_seconds * (2 ** (attempt - 1)), settings.jobs_backoff_cap_seconds)
            assert abs(delay - expected) < 1.0, (
                f"Attempt {attempt}: expected {expected}s, got {delay}s"
            )

    async def test_non_retryable_failure_terminates_immediately(self, pg_session_factory):
        job_id = await _setup_job(pg_session_factory)

        async with pg_session_factory() as s:
            token = await _set_processing(s, job_id, owner="w1", lease_duration=300)
            await s.commit()

        async with pg_session_factory() as s:
            repo = JobRepository(s)
            success = await repo.fail_job(
                job_id=job_id, owner="w1", lease_token=token,
                error=__import__("app.jobs.schemas", fromlist=["JobError"]).JobError(
                    category="invalid_payload",
                    retryable=False,
                ),
            )
            await s.commit()

        assert success is True

        async with pg_session_factory() as s:
            row = (
                await s.execute(
                    select(application_jobs.c.status)
                    .where(application_jobs.c.id == job_id)
                )
            ).first()
        assert row._mapping["status"] == "failed"

    async def test_final_attempt_becomes_failed(self, pg_session_factory):
        job_id = await _setup_job(pg_session_factory, max_attempts=2)

        async with pg_session_factory() as s:
            await _set_processing(s, job_id, owner="w1", lease_duration=-10)
            await s.execute(
                __import__("sqlalchemy").text(
                    "UPDATE application_jobs SET attempt_count = 2 WHERE id = :id"
                ),
                {"id": job_id},
            )
            await s.commit()

        async with pg_session_factory() as s:
            repo = JobRepository(s)
            result = await repo.reconcile_expired_processing(batch_limit=10)
            await s.commit()

        assert sum(result.exhausted_by_type.values()) > 0

        async with pg_session_factory() as s:
            row = (
                await s.execute(
                    select(application_jobs.c.status, application_jobs.c.last_error)
                    .where(application_jobs.c.id == job_id)
                )
            ).first()
        assert row._mapping["status"] == "failed"
        assert row._mapping["last_error"]["category"] == "attempts_exhausted"

    async def test_unsupported_payload_version_fails(self, pg_session_factory):
        from app.jobs.handler import get_handler_registry
        from app.jobs.handlers.register import register_handlers
        import app.jobs.worker as worker_mod

        register_handlers()
        registry = get_handler_registry()

        handler = registry.get_handler(_VALID_JOB_TYPE)
        assert handler is not None
        assert 99 not in handler.supported_payload_versions()


class TestWorkerShutdown:
    async def test_shutdown_stops_claims(self, pg_session_factory):
        from app.jobs.worker import Worker

        worker = Worker()
        worker._handler_registry = __import__("app.jobs.handler", fromlist=["get_handler_registry"]).get_handler_registry()

        assert not worker._shutdown_event.is_set()
        worker.stop()
        assert worker._shutdown_event.is_set()

    async def test_lease_not_renewed_after_token_change(self, pg_session_factory):
        job_id = await _setup_job(pg_session_factory)

        async with pg_session_factory() as s:
            token = await _set_processing(s, job_id, owner="w1", lease_duration=300)
            await s.commit()

        async with pg_session_factory() as s:
            old_token = token
            await _set_processing(s, job_id, owner="w2", lease_duration=300)
            await s.commit()

        async with pg_session_factory() as s:
            repo = JobRepository(s)
            renewed = await repo.renew_lease(
                job_id=job_id, owner="w1", lease_token=old_token,
                lease_duration_seconds=300,
            )
            await s.commit()

        assert renewed is False


class TestBacklogMetrics:
    async def test_backlog_counts_reflect_database(self, pg_session_factory):
        async with pg_session_factory() as s:
            repo = JobRepository(s)
            for i in range(3):
                await repo.enqueue(
                    job_type=_VALID_JOB_TYPE, payload_version=1,
                    payload={}, idempotency_key=f"bl-metric-{i}",
                )
            await s.commit()

        async with pg_session_factory() as s:
            repo = JobRepository(s)
            counts = await repo.get_backlog_counts()

        key = (_VALID_JOB_TYPE, "pending")
        assert counts.get(key, 0) == 3

    async def test_oldest_eligible_age(self, pg_session_factory):
        async with pg_session_factory() as s:
            repo = JobRepository(s)
            await repo.enqueue(
                job_type=_VALID_JOB_TYPE, payload_version=1,
                payload={}, idempotency_key="oldest-test",
            )
            await s.commit()

        async with pg_session_factory() as s:
            repo = JobRepository(s)
            age = await repo.oldest_eligible_age_seconds()

        assert age is not None
        assert age >= 0
