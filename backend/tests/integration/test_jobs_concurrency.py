import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select, text

from app.auth.tables import application_jobs
from app.jobs.repository import JobRepository
from app.jobs.schemas import JobError, JobFailureCategory, JobStatus, JobType

_VALID_JOB_TYPE = JobType.ingest_validated_claims.value


async def _enqueue_job(repo: JobRepository, key: str, **kw):
    return await repo.enqueue(
        job_type=_VALID_JOB_TYPE,
        payload_version=1,
        payload={"test": True},
        idempotency_key=key,
        **kw,
    )


async def _set_processing(session, job_id, owner="w1", lease_duration=300.0):
    token = str(uuid4())
    expires = datetime.now(timezone.utc) + timedelta(seconds=lease_duration)
    await session.execute(
        text("""
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


async def _get_lease(session, job_id):
    row = (
        await session.execute(
            select(
                application_jobs.c.lease_owner,
                application_jobs.c.lease_token,
                application_jobs.c.lease_expires_at,
                application_jobs.c.status,
            ).where(application_jobs.c.id == job_id)
        )
    ).first()
    return row._mapping if row else None


class TestConcurrentClaiming:
    async def test_two_workers_cannot_claim_same_job(self, pg_session_factory):
        async with pg_session_factory() as s:
            repo = JobRepository(s)
            job_id = await _enqueue_job(repo, "concurrent-claim-1")
            await s.commit()

        async with pg_session_factory() as s1, pg_session_factory() as s2:
            r1 = JobRepository(s1)
            r2 = JobRepository(s2)
            claimed1 = await r1.claim_jobs(owner="w1", batch_size=10, lease_duration_seconds=300)
            claimed2 = await r2.claim_jobs(owner="w2", batch_size=10, lease_duration_seconds=300)
            await s1.commit()
            await s2.commit()

        assert len(claimed1) == 1
        assert len(claimed2) == 0
        assert claimed1[0].id == job_id
        assert claimed1[0].lease_owner == "w1"

    async def test_second_worker_claims_after_lease_expiry(self, pg_session_factory):
        async with pg_session_factory() as s:
            repo = JobRepository(s)
            job_id = await _enqueue_job(repo, "expiry-claim")
            await s.commit()

        async with pg_session_factory() as s:
            await _set_processing(s, job_id, owner="w1", lease_duration=-10)
            await s.commit()

        async with pg_session_factory() as s:
            repo = JobRepository(s)
            claimed = await repo.claim_jobs(owner="w2", batch_size=10, lease_duration_seconds=300)
            await s.commit()

        assert len(claimed) == 1
        assert claimed[0].id == job_id
        assert claimed[0].lease_owner == "w2"

    async def test_expired_job_waits_for_recovery_backoff_before_claim(self, pg_session_factory, monkeypatch):
        monkeypatch.setenv("JOBS_BACKOFF_BASE_SECONDS", "5")
        monkeypatch.setenv("JOBS_BACKOFF_CAP_SECONDS", "10")
        from app.core.settings import get_settings

        get_settings.cache_clear()
        async with pg_session_factory() as s:
            repo = JobRepository(s)
            job_id = await _enqueue_job(repo, "recovery-boundary")
            await s.commit()

        async with pg_session_factory() as s:
            await _set_processing(s, job_id, owner="w1", lease_duration=-1)
            await s.commit()

        async with pg_session_factory() as s:
            claimed = await JobRepository(s).claim_jobs(
                owner="w2", batch_size=1, lease_duration_seconds=300
            )
            await s.rollback()
        assert claimed == []

        async with pg_session_factory() as s:
            await s.execute(
                text(
                    "UPDATE application_jobs "
                    "SET lease_expires_at = NOW() - INTERVAL '6 seconds' "
                    "WHERE id = :id"
                ),
                {"id": job_id},
            )
            await s.commit()

        async with pg_session_factory() as s:
            claimed = await JobRepository(s).claim_jobs(
                owner="w2", batch_size=1, lease_duration_seconds=300
            )
            await s.commit()
        assert [job.id for job in claimed] == [job_id]

    async def test_expired_job_uses_configured_recovery_backoff_cap(self, pg_session_factory, monkeypatch):
        monkeypatch.setenv("JOBS_BACKOFF_BASE_SECONDS", "1")
        monkeypatch.setenv("JOBS_BACKOFF_CAP_SECONDS", "5")
        from app.core.settings import get_settings

        get_settings.cache_clear()
        async with pg_session_factory() as s:
            repo = JobRepository(s)
            job_id = await _enqueue_job(repo, "recovery-cap", max_attempts=20)
            await s.commit()

        async with pg_session_factory() as s:
            await _set_processing(s, job_id, owner="w1", lease_duration=-1)
            await s.execute(
                text("UPDATE application_jobs SET attempt_count = 10 WHERE id = :id"),
                {"id": job_id},
            )
            await s.commit()

        async with pg_session_factory() as s:
            claimed = await JobRepository(s).claim_jobs(
                owner="w2", batch_size=1, lease_duration_seconds=300
            )
            await s.rollback()
        assert claimed == []

        async with pg_session_factory() as s:
            await s.execute(
                text(
                    "UPDATE application_jobs "
                    "SET lease_expires_at = NOW() - INTERVAL '6 seconds' "
                    "WHERE id = :id"
                ),
                {"id": job_id},
            )
            await s.commit()

        async with pg_session_factory() as s:
            claimed = await JobRepository(s).claim_jobs(
                owner="w2", batch_size=1, lease_duration_seconds=300
            )
            await s.commit()
        assert [job.id for job in claimed] == [job_id]

    async def test_stale_token_cannot_finalize_after_reassignment(self, pg_session_factory):
        async with pg_session_factory() as s:
            repo = JobRepository(s)
            job_id = await _enqueue_job(repo, "stale-reassign")
            await s.commit()

        async with pg_session_factory() as s:
            old_token = await _set_processing(s, job_id, owner="w1", lease_duration=-10)
            await s.commit()

        async with pg_session_factory() as s:
            repo = JobRepository(s)
            await repo.claim_jobs(owner="w2", batch_size=10, lease_duration_seconds=300)
            await s.commit()

        async with pg_session_factory() as s:
            repo = JobRepository(s)
            success = await repo.complete_job(
                job_id=job_id, owner="w1", lease_token=old_token
            )
            await s.commit()

        assert success is False, "Stale worker with old token must not finalize after reassignment"

    async def test_expired_token_cannot_finalize(self, pg_session_factory):
        async with pg_session_factory() as s:
            repo = JobRepository(s)
            job_id = await _enqueue_job(repo, "expired-token")
            await s.commit()

        async with pg_session_factory() as s:
            expired_token = await _set_processing(s, job_id, owner="w1", lease_duration=-10)
            await s.commit()

        async with pg_session_factory() as s:
            repo = JobRepository(s)
            success = await repo.complete_job(
                job_id=job_id, owner="w1", lease_token=expired_token
            )
            await s.commit()

        assert success is False, "Expired lease must reject finalization"

    async def test_renewed_lease_can_finalize(self, pg_session_factory):
        async with pg_session_factory() as s:
            repo = JobRepository(s)
            job_id = await _enqueue_job(repo, "renewed-finalize")
            await s.commit()

        async with pg_session_factory() as s:
            token = await _set_processing(s, job_id, owner="w1", lease_duration=300)
            await s.commit()

        async with pg_session_factory() as s:
            repo = JobRepository(s)
            renewed = await repo.renew_lease(
                job_id=job_id, owner="w1", lease_token=token, lease_duration_seconds=300
            )
            await s.commit()
            assert renewed is True

        async with pg_session_factory() as s:
            repo = JobRepository(s)
            success = await repo.complete_job(
                job_id=job_id, owner="w1", lease_token=token
            )
            await s.commit()

        assert success is True

    async def test_reassigned_lease_rejects_former_worker(self, pg_session_factory):
        async with pg_session_factory() as s:
            repo = JobRepository(s)
            job_id = await _enqueue_job(repo, "reassigned-reject")
            await s.commit()

        async with pg_session_factory() as s:
            old_token = await _set_processing(s, job_id, owner="w1", lease_duration=-10)
            await s.commit()

        async with pg_session_factory() as s:
            repo = JobRepository(s)
            _ = await repo.claim_jobs(owner="w2", batch_size=10, lease_duration_seconds=300)
            await s.commit()

        for op_name, op_fn in [
            ("complete", lambda r, tok: r.complete_job(job_id=job_id, owner="w1", lease_token=tok)),
            ("partial", lambda r, tok: r.partial_job(job_id=job_id, owner="w1", lease_token=tok)),
            ("retry", lambda r, tok: r.retry_job(
                job_id=job_id, owner="w1", lease_token=tok,
                error=JobError(
                    category=JobFailureCategory.provider_transient,
                    retryable=True,
                ),
                available_at=datetime.now(timezone.utc),
            )),
            ("fail", lambda r, tok: r.fail_job(
                job_id=job_id,
                owner="w1",
                lease_token=tok,
                error=JobError(
                    category=JobFailureCategory.invariant_violation,
                    retryable=False,
                ),
            )),
        ]:
            async with pg_session_factory() as s:
                repo = JobRepository(s)
                success = await op_fn(repo, old_token)
                await s.commit()
            assert success is False, f"{op_name} must reject former worker after reassignment"

    async def test_expired_transitions_are_rejected(self, pg_session_factory):
        async with pg_session_factory() as s:
            repo = JobRepository(s)
            job_id = await _enqueue_job(repo, "expired-reject-all")
            await s.commit()

        async with pg_session_factory() as s:
            token = await _set_processing(s, job_id, owner="w1", lease_duration=-30)
            await s.commit()

        for op_name, op_fn in [
            ("complete", lambda r: r.complete_job(job_id=job_id, owner="w1", lease_token=token)),
            ("partial", lambda r: r.partial_job(job_id=job_id, owner="w1", lease_token=token)),
            ("retry", lambda r: r.retry_job(
                job_id=job_id, owner="w1", lease_token=token,
                error=JobError(
                    category=JobFailureCategory.provider_transient,
                    retryable=True,
                ),
                available_at=datetime.now(timezone.utc),
            )),
            ("fail", lambda r: r.fail_job(
                job_id=job_id,
                owner="w1",
                lease_token=token,
                error=JobError(
                    category=JobFailureCategory.invariant_violation,
                    retryable=False,
                ),
            )),
        ]:
            async with pg_session_factory() as s:
                repo = JobRepository(s)
                success = await op_fn(repo)
                await s.commit()
            assert success is False, f"{op_name} must reject expired lease"


class TestClaimBatch:
    async def test_batch_size_is_enforced(self, pg_session_factory):
        async with pg_session_factory() as s:
            repo = JobRepository(s)
            for i in range(5):
                await _enqueue_job(repo, f"batch-size-{i}")
            await s.commit()

        async with pg_session_factory() as s:
            repo = JobRepository(s)
            claimed = await repo.claim_jobs(owner="w1", batch_size=3, lease_duration_seconds=300)
            await s.commit()

        assert len(claimed) == 3

    async def test_claim_respects_available_at(self, pg_session_factory):
        future = datetime.now(timezone.utc) + timedelta(hours=1)
        async with pg_session_factory() as s:
            repo = JobRepository(s)
            await _enqueue_job(repo, "future-job", available_at=future)
            await _enqueue_job(repo, "now-job")
            await s.commit()

        async with pg_session_factory() as s:
            repo = JobRepository(s)
            claimed = await repo.claim_jobs(owner="w1", batch_size=10, lease_duration_seconds=300)
            await s.commit()

        assert len(claimed) == 1

    async def test_claim_orders_by_available_at(self, pg_session_factory):
        earlier = datetime.now(timezone.utc) - timedelta(seconds=2)
        later = datetime.now(timezone.utc) - timedelta(seconds=1)
        async with pg_session_factory() as s:
            repo = JobRepository(s)
            id1 = await _enqueue_job(repo, "order-earlier", available_at=earlier)
            id2 = await _enqueue_job(repo, "order-later", available_at=later)
            await s.commit()

        async with pg_session_factory() as s:
            repo = JobRepository(s)
            claimed = await repo.claim_jobs(owner="w1", batch_size=10, lease_duration_seconds=300)
            await s.commit()

        assert len(claimed) == 2
        assert claimed[0].id == id1
        assert claimed[1].id == id2


class TestTransactionDurability:
    async def test_rollback_removes_enqueued_job(self, pg_session_factory):
        async with pg_session_factory() as s:
            repo = JobRepository(s)
            job_id = await _enqueue_job(repo, "rollback-test")
            await s.rollback()

        async with pg_session_factory() as s:
            row = (
                await s.execute(
                    select(application_jobs).where(application_jobs.c.id == job_id)
                )
            ).first()
        assert row is None

    async def test_committed_job_visible_from_new_session(self, pg_session_factory):
        async with pg_session_factory() as s:
            repo = JobRepository(s)
            job_id = await _enqueue_job(repo, "committed-visibility")
            await s.commit()

        async with pg_session_factory() as s:
            row = (
                await s.execute(
                    select(application_jobs).where(application_jobs.c.id == job_id)
                )
            ).first()
        assert row is not None
        assert row._mapping["idempotency_key"] == "committed-visibility"


class TestIdempotentEnqueue:
    async def test_concurrent_enqueue_returns_same_id(self, pg_session_factory):
        async def enqueue(payload_marker: int):
            async with pg_session_factory() as session:
                result = await JobRepository(session).enqueue_result(
                    job_type=_VALID_JOB_TYPE,
                    payload_version=1,
                    payload={"request": payload_marker},
                    idempotency_key="concurrent-enqueue",
                )
                await session.commit()
                return result

        first, second = await asyncio.gather(enqueue(1), enqueue(2))

        assert first.job_id == second.job_id
        assert {first.created, second.created} == {True, False}
        async with pg_session_factory() as session:
            rows = (
                await session.execute(
                    select(application_jobs.c.id).where(
                        application_jobs.c.job_type == _VALID_JOB_TYPE,
                        application_jobs.c.idempotency_key == "concurrent-enqueue",
                    )
                )
            ).all()
        assert [row._mapping["id"] for row in rows] == [first.job_id]

    async def test_enqueue_preserves_first_payload(self, pg_session_factory):
        async with pg_session_factory() as s:
            repo = JobRepository(s)
            id1 = await repo.enqueue(
                job_type=_VALID_JOB_TYPE, payload_version=1,
                payload={"original": True}, idempotency_key="payload-first",
            )
            id2 = await repo.enqueue(
                job_type=_VALID_JOB_TYPE, payload_version=1,
                payload={"overwrite": True}, idempotency_key="payload-first",
            )
            await s.commit()

        assert id1 == id2
        async with pg_session_factory() as s:
            row = (
                await s.execute(
                    select(application_jobs.c.payload).where(application_jobs.c.id == id1)
                )
            ).first()
        assert row._mapping["payload"] == {"original": True}


class TestReconciliation:
    async def test_exhausted_expired_jobs_become_failed(self, pg_session_factory):
        async with pg_session_factory() as s:
            repo = JobRepository(s)
            job_id = await repo.enqueue(
                job_type=_VALID_JOB_TYPE, payload_version=1,
                payload={}, idempotency_key="exhausted",
                max_attempts=2,
            )
            await s.commit()

        async with pg_session_factory() as s:
            await _set_processing(s, job_id, owner="w1", lease_duration=-10)
            await s.execute(
                text("UPDATE application_jobs SET attempt_count = 2 WHERE id = :id"),
                {"id": job_id},
            )
            await s.commit()

        async with pg_session_factory() as s:
            repo = JobRepository(s)
            result = await repo.reconcile_expired_processing(batch_limit=100)
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

    async def test_reconciliation_respects_batch_limit(self, pg_session_factory):
        async with pg_session_factory() as s:
            repo = JobRepository(s)
            for i in range(5):
                await _enqueue_job(repo, f"rec-batch-{i}")
            await s.commit()

        async with pg_session_factory() as s:
            repo = JobRepository(s)
            rows = await repo.claim_jobs(owner="w1", batch_size=5, lease_duration_seconds=-10)
            await s.commit()
        assert len(rows) == 5

        async with pg_session_factory() as s:
            repo = JobRepository(s)
            r1 = await repo.reconcile_expired_processing(batch_limit=2)
            await s.commit()
        assert sum(r1.recovered_by_type.values()) + sum(r1.exhausted_by_type.values()) == 2

        async with pg_session_factory() as s:
            repo = JobRepository(s)
            r2 = await repo.reconcile_expired_processing(batch_limit=2)
            await s.commit()
        assert sum(r2.recovered_by_type.values()) + sum(r2.exhausted_by_type.values()) == 2

        async with pg_session_factory() as s:
            repo = JobRepository(s)
            r3 = await repo.reconcile_expired_processing(batch_limit=2)
            await s.commit()
        assert sum(r3.recovered_by_type.values()) + sum(r3.exhausted_by_type.values()) == 1

    async def test_recovered_jobs_use_bounded_backoff(self, pg_session_factory):
        async with pg_session_factory() as s:
            repo = JobRepository(s)
            job_id = await _enqueue_job(repo, "backoff-recovery")
            await s.commit()

        async with pg_session_factory() as s:
            await _set_processing(s, job_id, owner="w1", lease_duration=-20)
            await s.commit()

        async with pg_session_factory() as s:
            repo = JobRepository(s)
            result = await repo.reconcile_expired_processing(batch_limit=10)
            await s.commit()
        assert sum(result.recovered_by_type.values()) > 0

        async with pg_session_factory() as s:
            row = (
                await s.execute(
                    select(application_jobs.c.status, application_jobs.c.available_at)
                    .where(application_jobs.c.id == job_id)
                )
            ).first()
        assert row._mapping["status"] == "pending"
        now = datetime.now(timezone.utc)
        assert now - timedelta(seconds=11) < row._mapping["available_at"] <= now

    async def test_direct_and_reconciled_recovery_use_same_absolute_eligibility(
        self, pg_session_factory, monkeypatch
    ):
        monkeypatch.setenv("JOBS_BACKOFF_BASE_SECONDS", "5")
        monkeypatch.setenv("JOBS_BACKOFF_CAP_SECONDS", "10")
        from app.core.settings import get_settings
        from app.jobs.repository import recovery_backoff_seconds

        get_settings.cache_clear()
        async with pg_session_factory() as s:
            repo = JobRepository(s)
            reconciled_job_id = await _enqueue_job(repo, "recovery-parity-reconciled")
            await s.commit()

        lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=10)
        async with pg_session_factory() as s:
            await s.execute(
                text(
                    """
                    UPDATE application_jobs
                    SET status = 'processing', attempt_count = 1,
                        lease_owner = 'w1', lease_token = :token,
                        lease_expires_at = :expires
                    WHERE id = :id
                    """
                ),
                {
                    "id": reconciled_job_id,
                    "token": str(uuid4()),
                    "expires": lease_expires_at,
                },
            )
            await s.commit()

        expected = lease_expires_at + timedelta(
            seconds=recovery_backoff_seconds(
                attempt_count=1,
                base=5,
                cap=10,
            )
        )
        async with pg_session_factory() as s:
            result = await JobRepository(s).reconcile_expired_processing(batch_limit=1)
            await s.commit()
            assert sum(result.recovered_by_type.values()) == 1
            available_at = await s.scalar(
                select(application_jobs.c.available_at).where(
                    application_jobs.c.id == reconciled_job_id
                )
            )

        assert abs((available_at - expected).total_seconds()) < 0.01

        async with pg_session_factory() as s:
            await s.execute(
                application_jobs.update()
                .where(application_jobs.c.id == reconciled_job_id)
                .values(status=JobStatus.failed.value)
            )
            direct_job_id = await _enqueue_job(
                JobRepository(s), "recovery-parity-direct"
            )
            await s.commit()
            await s.execute(
                text(
                    """
                    UPDATE application_jobs
                    SET status = 'processing', attempt_count = 1,
                        lease_owner = 'w1', lease_token = :token,
                        lease_expires_at = :expires
                    WHERE id = :id
                    """
                ),
                {
                    "id": direct_job_id,
                    "token": str(uuid4()),
                    "expires": lease_expires_at,
                },
            )
            await s.commit()

        async with pg_session_factory() as s:
            direct_claimed = await JobRepository(s).claim_jobs(
                owner="direct-worker",
                batch_size=1,
                lease_duration_seconds=300,
            )
            await s.commit()

        assert [job.id for job in direct_claimed] == [direct_job_id]
        assert direct_claimed[0].recovered is True

    async def test_two_workers_claim_recovered_job_only_once_after_backoff(
        self, pg_session_factory, monkeypatch
    ):
        monkeypatch.setenv("JOBS_BACKOFF_BASE_SECONDS", "1")
        monkeypatch.setenv("JOBS_BACKOFF_CAP_SECONDS", "1")
        from app.core.settings import get_settings

        get_settings.cache_clear()
        async with pg_session_factory() as s:
            repo = JobRepository(s)
            job_id = await _enqueue_job(repo, "recovery-race")
            await s.commit()
        async with pg_session_factory() as s:
            await _set_processing(s, job_id, owner="original", lease_duration=-2)
            await s.commit()

        async with pg_session_factory() as s1, pg_session_factory() as s2:
            first, second = await asyncio.gather(
                JobRepository(s1).claim_jobs(
                    owner="w1", batch_size=1, lease_duration_seconds=300
                ),
                JobRepository(s2).claim_jobs(
                    owner="w2", batch_size=1, lease_duration_seconds=300
                ),
            )
            await s1.commit()
            await s2.commit()

        claimed = [*first, *second]
        assert [job.id for job in claimed] == [job_id]
        assert claimed[0].recovered is True
