from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.auth.tables import application_jobs
from app.jobs.repository import JobRepository
from app.jobs.schemas import (
    JobError,
    JobFailureCategory,
    JobLimitation,
    JobType,
    ReadJobResult,
)

pytestmark = [
    pytest.mark.skipif(
        "SKIP_PG_TESTS" in __import__("os").environ,
        reason="PostgreSQL not available (SKIP_PG_TESTS is set)",
    ),
]

_VALID_JOB_TYPE = JobType.ingest_validated_claims.value


class TestSessionDurability:
    async def test_job_survives_session_replacement(self, pg_session_factory):
        async with pg_session_factory() as s:
            repo = JobRepository(s)
            job_id = await repo.enqueue(
                job_type=_VALID_JOB_TYPE, payload_version=1,
                payload={"durable": True},
                idempotency_key="survive-session",
            )
            await s.commit()

        async with pg_session_factory() as s:
            row = (
                await s.execute(
                    select(application_jobs).where(application_jobs.c.id == job_id)
                )
            ).first()
        assert row is not None
        assert row._mapping["status"] == "pending"

        async with pg_session_factory() as s:
            repo = JobRepository(s)
            claimed = await repo.claim_jobs(
                owner="w1", batch_size=10, lease_duration_seconds=300,
            )
            await s.commit()

        assert len(claimed) == 1
        assert claimed[0].id == job_id
        assert claimed[0].lease_owner == "w1"

    async def test_job_persists_across_transactions(self, pg_session_factory):
        session_ids = []
        for i in range(3):
            async with pg_session_factory() as s:
                repo = JobRepository(s)
                jid = await repo.enqueue(
                    job_type=_VALID_JOB_TYPE, payload_version=1,
                    payload={"seq": i},
                    idempotency_key=f"multi-tx-{i}",
                )
                await s.commit()
                session_ids.append(jid)

        async with pg_session_factory() as s:
            rows = (
                await s.execute(
                    select(application_jobs.c.id, application_jobs.c.payload)
                )
            ).all()
        db_ids = {row._mapping["id"] for row in rows}
        for jid in session_ids:
            assert jid in db_ids

    async def test_claim_and_commit_across_sessions(self, pg_session_factory):
        async with pg_session_factory() as s:
            repo = JobRepository(s)
            job_id = await repo.enqueue(
                job_type=_VALID_JOB_TYPE, payload_version=1,
                payload={"cross": True},
                idempotency_key="cross-session-claim",
            )
            await s.commit()

        async with pg_session_factory() as s:
            repo = JobRepository(s)
            _ = await repo.claim_jobs(
                owner="w1", batch_size=10, lease_duration_seconds=300,
            )
            await s.commit()

        async with pg_session_factory() as s:
            lease = (
                await s.execute(
                    select(
                        application_jobs.c.lease_owner,
                        application_jobs.c.lease_token,
                    ).where(application_jobs.c.id == job_id)
                )
            ).first()
            token = lease._mapping["lease_token"]

        async with pg_session_factory() as s:
            repo = JobRepository(s)
            success = await repo.complete_job(
                job_id=job_id, owner="w1", lease_token=token,
                result=ReadJobResult(succeeded=1),
            )
            await s.commit()

        assert success is True

        async with pg_session_factory() as s:
            row = (
                await s.execute(
                    select(
                        application_jobs.c.status,
                        application_jobs.c.result,
                        application_jobs.c.completed_at,
                    ).where(application_jobs.c.id == job_id)
                )
            ).first()
        assert row._mapping["status"] == "complete"
        assert row._mapping["result"]["succeeded"] == 1
        assert row._mapping["completed_at"] is not None


class TestCompleteResultPersistence:
    async def test_complete_with_result(self, pg_session_factory):
        async with pg_session_factory() as s:
            repo = JobRepository(s)
            job_id = await repo.enqueue(
                job_type=_VALID_JOB_TYPE, payload_version=1,
                payload={}, idempotency_key="complete-result",
            )
            await s.commit()

        async with pg_session_factory() as s:
            import sqlalchemy as sa

            token = str(uuid4())
            await s.execute(
                sa.text("""
                    UPDATE application_jobs
                    SET status = 'processing',
                        lease_owner = 'w1',
                        lease_token = :token,
                        lease_expires_at = :expires,
                        attempt_count = 1
                    WHERE id = :job_id
                """),
                {"token": token, "expires": datetime.now(timezone.utc) + timedelta(seconds=300), "job_id": job_id},
            )
            await s.commit()

        async with pg_session_factory() as s:
            repo = JobRepository(s)
            success = await repo.complete_job(
                job_id=job_id, owner="w1", lease_token=token,
                result=ReadJobResult(succeeded=3, skipped=1, failed=0),
            )
            await s.commit()

        assert success is True

        async with pg_session_factory() as s:
            row = (
                await s.execute(
                    select(application_jobs.c.result).where(application_jobs.c.id == job_id)
                )
            ).first()
        result = row._mapping["result"]
        assert result["succeeded"] == 3
        assert result["skipped"] == 1
        assert result["failed"] == 0

    async def test_partial_with_limitations(self, pg_session_factory):
        async with pg_session_factory() as s:
            repo = JobRepository(s)
            job_id = await repo.enqueue(
                job_type=_VALID_JOB_TYPE, payload_version=1,
                payload={}, idempotency_key="partial-limits",
            )
            await s.commit()

        async with pg_session_factory() as s:
            import sqlalchemy as sa

            token = str(uuid4())
            await s.execute(
                sa.text("""
                    UPDATE application_jobs
                    SET status = 'processing',
                        lease_owner = 'w1',
                        lease_token = :token,
                        lease_expires_at = :expires,
                        attempt_count = 1
                    WHERE id = :job_id
                """),
                {"token": token, "expires": datetime.now(timezone.utc) + timedelta(seconds=300), "job_id": job_id},
            )
            await s.commit()

        async with pg_session_factory() as s:
            repo = JobRepository(s)
            success = await repo.partial_job(
                job_id=job_id, owner="w1", lease_token=token,
                result=ReadJobResult(
                    succeeded=2,
                    skipped=0,
                    failed=1,
                    partial=True,
                    limitations=[JobLimitation.some_claims_failed],
                ),
            )
            await s.commit()

        assert success is True

        async with pg_session_factory() as s:
            row = (
                await s.execute(
                    select(application_jobs.c.result, application_jobs.c.status)
                    .where(application_jobs.c.id == job_id)
                )
            ).first()
        assert row._mapping["status"] == "partial"
        result = row._mapping["result"]
        assert result["succeeded"] == 2
        assert result["failed"] == 1
        assert result["limitations"] == ["some_claims_failed"]

    async def test_failed_with_sanitized_error(self, pg_session_factory):
        async with pg_session_factory() as s:
            repo = JobRepository(s)
            job_id = await repo.enqueue(
                job_type=_VALID_JOB_TYPE, payload_version=1,
                payload={}, idempotency_key="failed-error",
            )
            await s.commit()

        async with pg_session_factory() as s:
            import sqlalchemy as sa

            token = str(uuid4())
            await s.execute(
                sa.text("""
                    UPDATE application_jobs
                    SET status = 'processing',
                        lease_owner = 'w1',
                        lease_token = :token,
                        lease_expires_at = :expires,
                        attempt_count = 1
                    WHERE id = :job_id
                """),
                {"token": token, "expires": datetime.now(timezone.utc) + timedelta(seconds=300), "job_id": job_id},
            )
            await s.commit()

        async with pg_session_factory() as s:
            repo = JobRepository(s)
            success = await repo.fail_job(
                job_id=job_id, owner="w1", lease_token=token,
                error=JobError(
                    category=JobFailureCategory.provider_transient,
                    retryable=False,
                ),
                result=ReadJobResult(succeeded=0, failed=5),
            )
            await s.commit()

        assert success is True

        async with pg_session_factory() as s:
            row = (
                await s.execute(
                    select(application_jobs.c.status, application_jobs.c.last_error, application_jobs.c.result)
                    .where(application_jobs.c.id == job_id)
                )
            ).first()
        assert row._mapping["status"] == "failed"
        assert row._mapping["last_error"]["category"] == "provider_transient"
        assert row._mapping["last_error"]["retryable"] is False
        assert row._mapping["result"]["failed"] == 5
