"""Worker scenario tests that drive the real ``Worker`` class.

These tests use injectable session factories and a fake handler registry
so they exercise the polling, dispatch, lease renewal, lease loss,
drain, and shutdown paths without depending on the production
``IngestValidatedClaimsHandler``.
"""

from __future__ import annotations

import asyncio
import os
import signal
import socket
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, text

from app.auth.tables import application_jobs
from app.jobs.handler import (
    HandlerRegistry,
    JobHandler,
    JobHandlerResult,
    PermanentJobError,
    RetryableJobError,
    get_handler_registry,
)
from app.jobs.repository import JobRepository
from app.jobs.schemas import (
    IngestValidatedClaimsPayload,
    JobFailureCategory,
    JobLimitation,
    JobStatus,
    JobType,
    ReadJobResult,
)
from app.jobs.worker import Worker

pytestmark = [
    pytest.mark.skipif(
        "SKIP_PG_TESTS" in __import__("os").environ,
        reason="PostgreSQL not available (SKIP_PG_TESTS is set)",
    ),
]


@pytest.fixture(autouse=True)
def _settings(monkeypatch):
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
    monkeypatch.setenv("JOBS_SHUTDOWN_DRAIN_SECONDS", "2")
    monkeypatch.setenv("JOBS_METRICS_PORT", "0")
    from app.core.settings import get_settings
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


class _FakeHandler(JobHandler):
    """Handler that runs a script selected by ``_SCRIPT``."""

    _SCRIPT: list[Any] = []

    def __init__(self) -> None:
        self.calls: list[tuple[UUID, int, int]] = []

    def payload_model(self, payload_version: int):
        return IngestValidatedClaimsPayload

    async def handle(
        self, *, payload, attempt_count, max_attempts
    ) -> JobHandlerResult:
        self.calls.append((payload.conversation_id or uuid4(), attempt_count, max_attempts))
        for item in _FakeHandler._SCRIPT:
            outcome = item(self)
        return outcome


def _valid_payload() -> dict[str, Any]:
    return {
        "claims": [
            {
                "scientific_name": "Secretus plantus",
                "topic": "watering",
                "source_url": "https://secret.example/private-path",
                "source_domain": "secret.example",
                "source_provenance": "trusted",
                "claim": "SECRET_CLAIM_TEXT",
                "evidence_quote": "SECRET_EVIDENCE_QUOTE",
                "confidence": 0.9,
                "covered_aspects": ["watering_frequency_or_trigger"],
                "answerability_status": "full",
            }
        ],
        "conversation_id": "22222222-2222-2222-2222-222222222222",
        "answerability_status": "full",
    }


def _enqueue(pg_session_factory, *, idempotency_key: str | None = None) -> UUID:
    async def _do():
        async with pg_session_factory() as s:
            repo = JobRepository(s)
            job_id = await repo.enqueue(
                job_type=JobType.ingest_validated_claims.value,
                payload_version=1,
                payload=_valid_payload(),
                idempotency_key=idempotency_key or f"k-{uuid4()}",
            )
            await s.commit()
        return job_id

    return asyncio.get_event_loop().run_until_complete(_do())


async def _enqueue_async(pg_session_factory, *, idempotency_key: str | None = None) -> UUID:
    async with pg_session_factory() as s:
        repo = JobRepository(s)
        job_id = await repo.enqueue(
            job_type=JobType.ingest_validated_claims.value,
            payload_version=1,
            payload=_valid_payload(),
            idempotency_key=idempotency_key or f"k-{uuid4()}",
        )
        await s.commit()
    return job_id


async def _job_status(pg_session_factory, job_id: UUID) -> dict:
    async with pg_session_factory() as s:
        row = (
            await s.execute(
                select(
                    application_jobs.c.status,
                    application_jobs.c.attempt_count,
                    application_jobs.c.last_error,
                    application_jobs.c.lease_owner,
                    application_jobs.c.lease_token,
                    application_jobs.c.lease_expires_at,
                    application_jobs.c.available_at,
                    application_jobs.c.completed_at,
                ).where(application_jobs.c.id == job_id)
            )
        ).first()
    return dict(row._mapping) if row else {}


class TestWorkerPolling:
    async def test_successful_handler_completes_job(self, pg_session_factory):
        _FakeHandler._SCRIPT = [
            lambda _h: JobHandlerResult(
                status=JobStatus.complete,
                result=ReadJobResult(succeeded=1),
            )
        ]
        handler = _FakeHandler()
        registry = HandlerRegistry()
        registry.register(
            JobType.ingest_validated_claims.value,
            handler,
            payload_models={1: IngestValidatedClaimsPayload},
        )
        worker = Worker(
            session_factory=pg_session_factory,
            handler_registry=registry,
        )
        job_id = await _enqueue_async(pg_session_factory)

        task = asyncio.create_task(worker.start())
        # Wait for the job to be claimed and finalized.
        for _ in range(60):
            row = await _job_status(pg_session_factory, job_id)
            if row.get("status") == JobStatus.complete.value:
                break
            await asyncio.sleep(0.05)
        worker.stop()
        await task

        row = await _job_status(pg_session_factory, job_id)
        assert row["status"] == JobStatus.complete.value
        assert handler.calls, "handler should have been invoked"

    async def test_partial_handler_records_partial_status(self, pg_session_factory):
        _FakeHandler._SCRIPT = [
            lambda _h: JobHandlerResult(
                status=JobStatus.partial,
                result=ReadJobResult(
                    succeeded=1, failed=1, partial=True,
                    limitations=[JobLimitation.some_claims_failed],
                ),
            )
        ]
        handler = _FakeHandler()
        registry = HandlerRegistry()
        registry.register(
            JobType.ingest_validated_claims.value,
            handler,
            payload_models={1: IngestValidatedClaimsPayload},
        )
        worker = Worker(
            session_factory=pg_session_factory,
            handler_registry=registry,
        )
        job_id = await _enqueue_async(pg_session_factory)

        task = asyncio.create_task(worker.start())
        for _ in range(60):
            row = await _job_status(pg_session_factory, job_id)
            if row.get("status") == JobStatus.partial.value:
                break
            await asyncio.sleep(0.05)
        worker.stop()
        await task

        row = await _job_status(pg_session_factory, job_id)
        assert row["status"] == JobStatus.partial.value

    @pytest.mark.parametrize("invalid_result", [
        JobHandlerResult(status=JobStatus.partial),
        JobHandlerResult(
            status=JobStatus.partial,
            result=ReadJobResult(succeeded=1, partial=False),
        ),
        JobHandlerResult(
            status=JobStatus.partial,
            result=ReadJobResult(succeeded=1, partial=True),
        ),
    ])
    async def test_invalid_partial_result_contract_fails_terminally(
        self, pg_session_factory, invalid_result
    ):
        _FakeHandler._SCRIPT = [lambda _h: invalid_result]
        registry = HandlerRegistry()
        registry.register(
            JobType.ingest_validated_claims.value,
            _FakeHandler(),
            payload_models={1: IngestValidatedClaimsPayload},
        )
        job_id = await _enqueue_async(pg_session_factory)
        worker = Worker(session_factory=pg_session_factory, handler_registry=registry)
        task = asyncio.create_task(worker.start())
        for _ in range(60):
            row = await _job_status(pg_session_factory, job_id)
            if row.get("status") == JobStatus.failed.value:
                break
            await asyncio.sleep(0.05)
        worker.stop()
        await task

        row = await _job_status(pg_session_factory, job_id)
        assert row["status"] == JobStatus.failed.value
        assert row["last_error"] == {
            "category": JobFailureCategory.invariant_violation.value,
            "retryable": False,
        }

    async def test_retryable_failure_returns_to_pending(self, pg_session_factory):
        from app.jobs.worker import JobFailureCategory

        _FakeHandler._SCRIPT = [
            lambda _h: JobHandlerResult.failed(
                category=JobFailureCategory.provider_transient,
                retryable=True,
            )
        ]
        handler = _FakeHandler()
        registry = HandlerRegistry()
        registry.register(
            JobType.ingest_validated_claims.value,
            handler,
            payload_models={1: IngestValidatedClaimsPayload},
        )
        worker = Worker(
            session_factory=pg_session_factory,
            handler_registry=registry,
        )
        job_id = await _enqueue_async(pg_session_factory, idempotency_key="retry-test")

        task = asyncio.create_task(worker.start())
        for _ in range(60):
            row = await _job_status(pg_session_factory, job_id)
            if row.get("status") == JobStatus.pending.value and row.get("attempt_count", 0) >= 1:
                break
            await asyncio.sleep(0.05)
        worker.stop()
        await task

        row = await _job_status(pg_session_factory, job_id)
        assert row["status"] == JobStatus.pending.value
        assert row["attempt_count"] == 1

    async def test_real_worker_applies_exponential_retry_delay_and_cap(
        self, pg_session_factory, monkeypatch
    ):
        monkeypatch.setenv("JOBS_POLL_INTERVAL_SECONDS", "0.02")
        monkeypatch.setenv("JOBS_BACKOFF_BASE_SECONDS", "0.05")
        monkeypatch.setenv("JOBS_BACKOFF_CAP_SECONDS", "0.10")
        monkeypatch.setenv("JOBS_MAX_ATTEMPTS_DEFAULT", "4")
        from app.core.settings import get_settings

        get_settings.cache_clear()

        class _ScriptedHandler(JobHandler):
            def __init__(self) -> None:
                self.invocations: list[tuple[object, object]] = []

            async def handle(self, *, payload, attempt_count, max_attempts):
                async with pg_session_factory() as session:
                    invocation_time = await session.scalar(select(func.clock_timestamp()))
                    eligible_at = await session.scalar(
                        select(application_jobs.c.available_at).where(
                            application_jobs.c.idempotency_key == "retry-timing"
                        )
                    )
                self.invocations.append((invocation_time, eligible_at))
                if attempt_count < 4:
                    return JobHandlerResult.failed(
                        category=JobFailureCategory.provider_transient,
                        retryable=True,
                    )
                return JobHandlerResult(
                    status=JobStatus.complete,
                    result=ReadJobResult(succeeded=1),
                )

        handler = _ScriptedHandler()
        registry = HandlerRegistry()
        registry.register(
            JobType.ingest_validated_claims.value,
            handler,
            payload_models={1: IngestValidatedClaimsPayload},
        )
        job_id = await _enqueue_async(pg_session_factory, idempotency_key="retry-timing")
        worker = Worker(
            session_factory=pg_session_factory,
            handler_registry=registry,
            settings=get_settings(),
        )
        task = asyncio.create_task(worker.start())
        try:
            async with asyncio.timeout(5):
                while (await _job_status(pg_session_factory, job_id)).get("status") != "complete":
                    await asyncio.sleep(0.02)
        finally:
            worker.stop()
            await task

        row = await _job_status(pg_session_factory, job_id)
        assert row["attempt_count"] == 4
        assert row["status"] == JobStatus.complete.value
        assert len(handler.invocations) == 4
        assert all(
            invocation_time >= eligible_at
            for invocation_time, eligible_at in handler.invocations[1:]
        )
        delays = [
            (next_eligible - invocation_time).total_seconds()
            for (invocation_time, _), (_, next_eligible) in zip(
                handler.invocations,
                handler.invocations[1:],
            )
        ]
        assert delays == pytest.approx([0.05, 0.10, 0.10], abs=0.04)

    async def test_retryable_failure_on_final_attempt_becomes_failed(
        self, pg_session_factory
    ):
        _FakeHandler._SCRIPT = [
            lambda _h: JobHandlerResult.failed(
                category=JobFailureCategory.provider_transient,
                retryable=True,
            )
        ]
        handler = _FakeHandler()
        registry = HandlerRegistry()
        registry.register(
            JobType.ingest_validated_claims.value,
            handler,
            payload_models={1: IngestValidatedClaimsPayload},
        )
        async with pg_session_factory() as session:
            job_id = await JobRepository(session).enqueue(
                job_type=JobType.ingest_validated_claims.value,
                payload_version=1,
                payload=_valid_payload(),
                idempotency_key="final-attempt",
                max_attempts=1,
            )
            await session.commit()

        worker = Worker(session_factory=pg_session_factory, handler_registry=registry)
        task = asyncio.create_task(worker.start())
        for _ in range(60):
            row = await _job_status(pg_session_factory, job_id)
            if row.get("status") == JobStatus.failed.value:
                break
            await asyncio.sleep(0.05)
        worker.stop()
        await task

        row = await _job_status(pg_session_factory, job_id)
        assert row["status"] == JobStatus.failed.value
        assert row["attempt_count"] == 1
        assert row["last_error"] == {
            "category": "provider_transient",
            "retryable": False,
        }
        assert row["completed_at"] is not None

    async def test_permanent_failure_terminates_immediately(self, pg_session_factory):
        from app.jobs.worker import JobFailureCategory

        _FakeHandler._SCRIPT = [
            lambda _h: JobHandlerResult.failed(
                category=JobFailureCategory.invalid_payload,
                retryable=False,
            )
        ]
        handler = _FakeHandler()
        registry = HandlerRegistry()
        registry.register(
            JobType.ingest_validated_claims.value,
            handler,
            payload_models={1: IngestValidatedClaimsPayload},
        )
        worker = Worker(
            session_factory=pg_session_factory,
            handler_registry=registry,
        )
        job_id = await _enqueue_async(pg_session_factory, idempotency_key="perm-fail")

        task = asyncio.create_task(worker.start())
        for _ in range(60):
            row = await _job_status(pg_session_factory, job_id)
            if row.get("status") == JobStatus.failed.value:
                break
            await asyncio.sleep(0.05)
        worker.stop()
        await task

        row = await _job_status(pg_session_factory, job_id)
        assert row["status"] == JobStatus.failed.value
        assert row["last_error"]["category"] == "invalid_payload"

    @pytest.mark.parametrize(
        ("raised", "max_attempts", "expected_status", "category", "retryable"),
        [
            (
                RuntimeError("SECRET_RAW_EXCEPTION"),
                3,
                JobStatus.pending.value,
                JobFailureCategory.unexpected_error.value,
                True,
            ),
            (
                RuntimeError("SECRET_RAW_EXCEPTION"),
                1,
                JobStatus.failed.value,
                JobFailureCategory.unexpected_error.value,
                False,
            ),
            (
                RetryableJobError(JobFailureCategory.provider_transient),
                3,
                JobStatus.pending.value,
                JobFailureCategory.provider_transient.value,
                True,
            ),
            (
                PermanentJobError(JobFailureCategory.invariant_violation),
                3,
                JobStatus.failed.value,
                JobFailureCategory.invariant_violation.value,
                False,
            ),
        ],
    )
    async def test_raised_handler_errors_are_sanitized_and_finalized(
        self,
        pg_session_factory,
        caplog,
        raised,
        max_attempts,
        expected_status,
        category,
        retryable,
    ):
        class _RaisingHandler(JobHandler):
            def payload_model(self, payload_version: int):
                return IngestValidatedClaimsPayload

            async def handle(self, *, payload, attempt_count, max_attempts):
                raise raised

        registry = HandlerRegistry()
        registry.register(
            JobType.ingest_validated_claims.value,
            _RaisingHandler(),
            payload_models={1: IngestValidatedClaimsPayload},
        )
        async with pg_session_factory() as session:
            job_id = await JobRepository(session).enqueue(
                job_type=JobType.ingest_validated_claims.value,
                payload_version=1,
                payload=_valid_payload(),
                idempotency_key=f"raised-{uuid4()}",
                max_attempts=max_attempts,
            )
            await session.commit()

        import logging

        caplog.set_level(logging.INFO, logger="app.jobs.worker")
        worker = Worker(session_factory=pg_session_factory, handler_registry=registry)
        task = asyncio.create_task(worker.start())
        for _ in range(60):
            row = await _job_status(pg_session_factory, job_id)
            if row.get("status") == expected_status and row.get("attempt_count") == 1:
                break
            await asyncio.sleep(0.05)
        worker.stop()
        await task

        row = await _job_status(pg_session_factory, job_id)
        assert row["status"] == expected_status
        assert row["last_error"] == {"category": category, "retryable": retryable}
        assert "SECRET_RAW_EXCEPTION" not in str(row["last_error"])
        assert "SECRET_RAW_EXCEPTION" not in " ".join(
            str(record.__dict__) for record in caplog.records
        )

    async def test_unsupported_version_fails_without_task_exception(
        self, pg_session_factory, caplog
    ):
        _FakeHandler._SCRIPT = [
            lambda _h: JobHandlerResult(
                status=JobStatus.complete,
                result=ReadJobResult(succeeded=0),
            )
        ]
        handler = _FakeHandler()
        registry = HandlerRegistry()
        registry.register(
            JobType.ingest_validated_claims.value,
            handler,
            payload_models={1: IngestValidatedClaimsPayload},
        )
        # Enqueue with payload_version=99 which is not in payload_models.
        job_id = uuid4()
        payload = _valid_payload()
        payload["claims"][0]["claim"] = "SENSITIVE_UNSUPPORTED_PAYLOAD"
        async with pg_session_factory() as s:
            from sqlalchemy.dialects.postgresql import insert as pg_insert
            await s.execute(
                pg_insert(application_jobs).values(
                    id=job_id,
                    job_type=JobType.ingest_validated_claims.value,
                    payload_version=99,
                    payload=payload,
                    status=JobStatus.pending.value,
                    idempotency_key=f"unsupp-{uuid4()}",
                    max_attempts=3,
                    available_at=datetime.now(timezone.utc),
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )
            )
            await s.commit()

        worker = Worker(
            session_factory=pg_session_factory,
            handler_registry=registry,
        )

        import logging

        caplog.set_level(logging.INFO, logger="app.jobs.worker")
        task = asyncio.create_task(worker.start())
        # The unsupported version claim should fail immediately.
        await asyncio.sleep(0.5)
        worker.stop()
        await task

        row = await _job_status(pg_session_factory, job_id)
        assert row["status"] == JobStatus.failed.value
        assert row["last_error"] == {
            "category": "unsupported_payload_version",
            "retryable": False,
        }
        assert handler.calls == []
        assert "SENSITIVE_UNSUPPORTED_PAYLOAD" not in " ".join(
            str(record.__dict__) for record in caplog.records
        )

    async def test_invalid_payload_fails_before_handler_execution(
        self, pg_session_factory
    ):
        handler = _FakeHandler()
        registry = HandlerRegistry()
        registry.register(
            JobType.ingest_validated_claims.value,
            handler,
            payload_models={1: IngestValidatedClaimsPayload},
        )
        async with pg_session_factory() as session:
            job_id = await JobRepository(session).enqueue(
                job_type=JobType.ingest_validated_claims.value,
                payload_version=1,
                payload={
                    "claims": [],
                    "conversation_id": str(uuid4()),
                    "answerability_status": "full",
                },
                idempotency_key="invalid-empty-claims",
            )
            await session.commit()

        worker = Worker(
            session_factory=pg_session_factory,
            handler_registry=registry,
        )
        task = asyncio.create_task(worker.start())
        for _ in range(60):
            row = await _job_status(pg_session_factory, job_id)
            if row.get("status") == JobStatus.failed.value:
                break
            await asyncio.sleep(0.05)
        worker.stop()
        await task

        row = await _job_status(pg_session_factory, job_id)
        assert row["status"] == JobStatus.failed.value
        assert row["last_error"] == {
            "category": "invalid_payload",
            "retryable": False,
        }
        assert handler.calls == []

    async def test_column_payload_version_mismatch_fails_before_handler_execution(
        self, pg_session_factory
    ):
        handler = _FakeHandler()
        registry = HandlerRegistry()
        registry.register(
            JobType.ingest_validated_claims.value,
            handler,
            payload_models={1: IngestValidatedClaimsPayload},
        )
        payload = _valid_payload()
        payload["payload_version"] = 2
        async with pg_session_factory() as session:
            job_id = await JobRepository(session).enqueue(
                job_type=JobType.ingest_validated_claims.value,
                payload_version=1,
                payload=payload,
                idempotency_key=f"column-body-mismatch-{uuid4()}",
            )
            await session.commit()
        worker = Worker(session_factory=pg_session_factory, handler_registry=registry)
        task = asyncio.create_task(worker.start())
        try:
            async with asyncio.timeout(3):
                while (await _job_status(pg_session_factory, job_id)).get("status") != "failed":
                    await asyncio.sleep(0.02)
        finally:
            worker.stop()
            await task
        row = await _job_status(pg_session_factory, job_id)
        assert row["last_error"] == {
            "category": JobFailureCategory.invalid_payload.value,
            "retryable": False,
        }
        assert handler.calls == []

    async def test_one_poll_fills_concurrency_across_multiple_batches(
        self, pg_session_factory, monkeypatch
    ):
        monkeypatch.setenv("JOBS_BATCH_SIZE", "2")
        monkeypatch.setenv("JOBS_WORKER_CONCURRENCY", "5")
        from app.core.settings import get_settings

        get_settings.cache_clear()
        started_count = 0
        all_started = asyncio.Event()
        release = asyncio.Event()

        class _CapacityHandler(JobHandler):
            def payload_model(self, payload_version: int):
                return IngestValidatedClaimsPayload

            async def handle(self, *, payload, attempt_count, max_attempts):
                nonlocal started_count
                started_count += 1
                if started_count == 5:
                    all_started.set()
                await release.wait()
                return JobHandlerResult(
                    status=JobStatus.complete,
                    result=ReadJobResult(succeeded=1),
                )

        registry = HandlerRegistry()
        registry.register(
            JobType.ingest_validated_claims.value,
            _CapacityHandler(),
            payload_models={1: IngestValidatedClaimsPayload},
        )
        job_ids = [
            await _enqueue_async(pg_session_factory, idempotency_key=f"capacity-{index}")
            for index in range(5)
        ]
        worker = Worker(session_factory=pg_session_factory, handler_registry=registry)

        task = asyncio.create_task(worker.start())
        await asyncio.wait_for(all_started.wait(), timeout=3.0)
        assert len(worker.active_executions()) == 5
        release.set()
        for _ in range(60):
            rows = [await _job_status(pg_session_factory, job_id) for job_id in job_ids]
            if all(row["status"] == JobStatus.complete.value for row in rows):
                break
            await asyncio.sleep(0.05)
        worker.stop()
        await task

        assert started_count == 5

    @pytest.mark.asyncio(loop_scope="function")
    async def test_empty_poll_waits_for_configured_interval(self, monkeypatch):
        monkeypatch.setenv("JOBS_POLL_INTERVAL_SECONDS", "0.2")
        from app.core.settings import get_settings

        get_settings.cache_clear()
        worker = Worker(settings=get_settings(), handler_registry=HandlerRegistry())
        assert worker.settings.jobs_poll_interval_seconds == 0.2
        assert not worker._shutdown_event.is_set()
        poll_times: list[float] = []

        async def reconcile() -> None:
            poll_times.append(asyncio.get_running_loop().time())
            if len(poll_times) == 2:
                worker.stop()

        worker._reconcile = reconcile
        worker._claim_batch = AsyncMock()
        worker._claim_additional_if_capacity = AsyncMock(return_value=False)

        await asyncio.wait_for(worker._poll_loop(), timeout=1.0)

        assert len(poll_times) == 2
        assert poll_times[1] - poll_times[0] >= 0.18

    async def test_active_handler_renews_lease(
        self, pg_session_factory, monkeypatch, caplog
    ):
        monkeypatch.setenv("JOBS_LEASE_DURATION_SECONDS", "0.6")
        monkeypatch.setenv("JOBS_LEASE_RENEWAL_INTERVAL_SECONDS", "0.1")
        from app.core.settings import get_settings

        get_settings.cache_clear()
        started = asyncio.Event()
        release = asyncio.Event()

        class _LongHandler(JobHandler):
            def payload_model(self, payload_version: int):
                return IngestValidatedClaimsPayload

            async def handle(self, *, payload, attempt_count, max_attempts):
                started.set()
                await release.wait()
                return JobHandlerResult(
                    status=JobStatus.complete,
                    result=ReadJobResult(succeeded=1),
                )

        registry = HandlerRegistry()
        registry.register(
            JobType.ingest_validated_claims.value,
            _LongHandler(),
            payload_models={1: IngestValidatedClaimsPayload},
        )
        worker = Worker(session_factory=pg_session_factory, handler_registry=registry)
        job_id = await _enqueue_async(pg_session_factory)

        import logging

        caplog.set_level(logging.INFO, logger="app.jobs.worker")
        task = asyncio.create_task(worker.start())
        await asyncio.wait_for(started.wait(), timeout=3.0)
        initial_expiry = (await _job_status(pg_session_factory, job_id))["lease_expires_at"]
        await asyncio.sleep(0.25)
        renewed_expiry = (await _job_status(pg_session_factory, job_id))["lease_expires_at"]
        release.set()
        for _ in range(60):
            if (await _job_status(pg_session_factory, job_id))["status"] == JobStatus.complete.value:
                break
            await asyncio.sleep(0.05)
        worker.stop()
        await task

        assert renewed_expiry > initial_expiry
        assert (await _job_status(pg_session_factory, job_id))["status"] == JobStatus.complete.value
        renewed_record = next(
            record for record in caplog.records if record.message == "job_lease_renewed"
        )
        assert renewed_record.__dict__["ctx_job_type"] == JobType.ingest_validated_claims.value
        assert renewed_record.__dict__["ctx_attempt"] == 1
        assert renewed_record.__dict__["ctx_worker_identity"] == worker.owner
        rendered_logs = " ".join(str(record.__dict__) for record in caplog.records)
        for sentinel in (
            "https://secret.example/private-path",
            "Secretus plantus",
            "SECRET_CLAIM_TEXT",
            "SECRET_EVIDENCE_QUOTE",
            "22222222-2222-2222-2222-222222222222",
        ):
            assert sentinel not in rendered_logs

    async def test_lease_loss_suppresses_stale_finalization(
        self, pg_session_factory, monkeypatch, caplog
    ):
        monkeypatch.setenv("JOBS_LEASE_DURATION_SECONDS", "0.6")
        monkeypatch.setenv("JOBS_LEASE_RENEWAL_INTERVAL_SECONDS", "0.1")
        from app.core.settings import get_settings

        get_settings.cache_clear()
        started = asyncio.Event()
        release = asyncio.Event()

        class _LongHandler(JobHandler):
            def payload_model(self, payload_version: int):
                return IngestValidatedClaimsPayload

            async def handle(self, *, payload, attempt_count, max_attempts):
                started.set()
                await release.wait()
                return JobHandlerResult(
                    status=JobStatus.complete,
                    result=ReadJobResult(succeeded=1),
                )

        registry = HandlerRegistry()
        registry.register(
            JobType.ingest_validated_claims.value,
            _LongHandler(),
            payload_models={1: IngestValidatedClaimsPayload},
        )
        from app.observability.metrics import MetricsRegistry

        metrics = MetricsRegistry()
        worker = Worker(
            session_factory=pg_session_factory,
            handler_registry=registry,
            metrics=metrics,
        )
        job_id = await _enqueue_async(pg_session_factory)

        import logging

        caplog.set_level(logging.INFO, logger="app.jobs.worker")
        task = asyncio.create_task(worker.start())
        await asyncio.wait_for(started.wait(), timeout=3.0)
        replacement_token = "SECRET_LEASE_TOKEN"
        async with pg_session_factory() as session:
            await session.execute(
                application_jobs.update()
                .where(application_jobs.c.id == job_id)
                .values(
                    lease_owner="replacement-worker",
                    lease_token=replacement_token,
                    lease_expires_at=datetime.now(timezone.utc) + timedelta(seconds=5),
                )
            )
            await session.commit()

        for _ in range(40):
            state = worker._executions.get(str(job_id))
            if state is not None and state.lease_lost:
                break
            await asyncio.sleep(0.05)
        else:
            release.set()
            worker.stop()
            await task
            pytest.fail("worker did not detect lease loss")

        release.set()
        await asyncio.sleep(0.1)
        worker.stop()
        await task

        row = await _job_status(pg_session_factory, job_id)
        assert row["status"] == JobStatus.processing.value
        assert row["lease_owner"] == "replacement-worker"
        assert row["lease_token"] == replacement_token
        lost_record = next(
            record
            for record in caplog.records
            if record.message in {"job_lease_lost", "worker_lease_lost"}
        )
        assert lost_record.__dict__["ctx_job_type"] == JobType.ingest_validated_claims.value
        assert lost_record.__dict__["ctx_attempt"] == 1
        assert lost_record.__dict__["ctx_worker_identity"] == worker.owner
        assert lost_record.__dict__["ctx_operation"] in {"renewal", "execution"}
        assert "SECRET_LEASE_TOKEN" not in " ".join(
            str(record.__dict__) for record in caplog.records
        )
        assert metrics.job_outcomes[
            (JobType.ingest_validated_claims.value, "lease_lost")
        ] == 1
        histogram = metrics.job_duration_histograms[
            (JobType.ingest_validated_claims.value, "lease_lost")
        ]
        assert histogram.total_count == 1
        assert histogram.total_sum >= 0

    async def test_finalization_lease_loss_records_one_bounded_outcome(
        self, pg_session_factory, caplog
    ):
        import logging

        from app.observability.metrics import MetricsRegistry

        job_id = await _enqueue_async(
            pg_session_factory, idempotency_key="finalization-lease-loss"
        )
        replacement_token = "SECRET_LEASE_TOKEN"

        class _ReplaceLeaseHandler(JobHandler):
            def payload_model(self, payload_version: int):
                return IngestValidatedClaimsPayload

            async def handle(self, *, payload, attempt_count, max_attempts):
                async with pg_session_factory() as session:
                    await session.execute(
                        application_jobs.update()
                        .where(application_jobs.c.id == job_id)
                        .values(
                            lease_owner="replacement-worker",
                            lease_token=replacement_token,
                            lease_expires_at=datetime.now(timezone.utc)
                            + timedelta(seconds=30),
                        )
                    )
                    await session.commit()
                return JobHandlerResult(
                    status=JobStatus.complete,
                    result=ReadJobResult(succeeded=1),
                )

        registry = HandlerRegistry()
        registry.register(
            JobType.ingest_validated_claims.value,
            _ReplaceLeaseHandler(),
            payload_models={1: IngestValidatedClaimsPayload},
        )
        metrics = MetricsRegistry()
        worker = Worker(
            session_factory=pg_session_factory,
            handler_registry=registry,
            metrics=metrics,
        )
        caplog.set_level(logging.INFO, logger="app.jobs.worker")

        task = asyncio.create_task(worker.start())
        async with asyncio.timeout(3.0):
            while metrics.job_outcomes.get(
                (JobType.ingest_validated_claims.value, "lease_lost")
            ) != 1:
                await asyncio.sleep(0.02)
        worker.stop()
        await task

        row = await _job_status(pg_session_factory, job_id)
        assert row["status"] == JobStatus.processing.value
        assert row["lease_owner"] == "replacement-worker"
        assert row["lease_token"] == replacement_token
        lost_record = next(
            record for record in caplog.records if record.message == "worker_lease_lost"
        )
        assert lost_record.__dict__["ctx_operation"] == "complete"
        assert replacement_token not in " ".join(
            str(record.__dict__) for record in caplog.records
        )
        assert metrics.job_outcomes[
            (JobType.ingest_validated_claims.value, "lease_lost")
        ] == 1
        histogram = metrics.job_duration_histograms[
            (JobType.ingest_validated_claims.value, "lease_lost")
        ]
        assert histogram.total_count == 1
        assert histogram.total_sum >= 0


class TestShutdownDuringClaim:
    async def test_shutdown_before_commit_rolls_back(
        self, pg_session_factory, monkeypatch, caplog
    ):
        import logging
        from unittest.mock import patch

        monkeypatch.setenv("JOBS_BATCH_SIZE", "10")
        monkeypatch.setenv("JOBS_WORKER_CONCURRENCY", "5")
        from app.core.settings import get_settings
        get_settings.cache_clear()
        handler = _FakeHandler()
        _FakeHandler._SCRIPT = [
            lambda _h: JobHandlerResult(
                status=JobStatus.complete,
                result=ReadJobResult(succeeded=1),
            )
        ]
        registry = HandlerRegistry()
        registry.register(
            JobType.ingest_validated_claims.value,
            handler,
            payload_models={1: IngestValidatedClaimsPayload},
        )
        job_id = await _enqueue_async(pg_session_factory, idempotency_key="shutdown-bc")

        worker = Worker(
            session_factory=pg_session_factory,
            handler_registry=registry,
        )
        claim_finished = asyncio.Event()
        allow_return = asyncio.Event()
        claimed_ids = []
        original_claim_jobs = JobRepository.claim_jobs

        async def blocked_claim_jobs(
            repository,
            *,
            owner,
            batch_size,
            lease_duration_seconds,
        ):
            result = await original_claim_jobs(
                repository,
                owner=owner,
                batch_size=batch_size,
                lease_duration_seconds=lease_duration_seconds,
            )
            claimed_ids.extend(job.id for job in result)
            claim_finished.set()
            await allow_return.wait()
            return result

        caplog.set_level(logging.INFO, logger="app.jobs.worker")
        with patch.object(JobRepository, "claim_jobs", blocked_claim_jobs):
            task = asyncio.create_task(worker.start())
            await asyncio.wait_for(claim_finished.wait(), timeout=5)
            worker.stop()
            allow_return.set()
            await task

        row = await _job_status(pg_session_factory, job_id)
        assert claimed_ids == [job_id]
        assert row["status"] == JobStatus.pending.value
        assert row["attempt_count"] == 0
        assert row["lease_owner"] is None
        assert row["lease_token"] is None
        assert row["lease_expires_at"] is None
        assert handler.calls == []
        assert worker.active_executions() == []
        assert worker._handler_tasks == {}
        assert worker._renewal_tasks == {}
        assert not any(
            record.message == "worker_poll_failed" for record in caplog.records
        )

    async def test_shutdown_after_commit_releases_lease(
        self, pg_session_factory, monkeypatch, caplog
    ):
        import logging
        from unittest.mock import patch
        from sqlalchemy.ext.asyncio import AsyncSession

        monkeypatch.setenv("JOBS_BATCH_SIZE", "10")
        monkeypatch.setenv("JOBS_WORKER_CONCURRENCY", "5")
        from app.core.settings import get_settings
        get_settings.cache_clear()
        handler = _FakeHandler()
        _FakeHandler._SCRIPT = [
            lambda _h: JobHandlerResult(
                status=JobStatus.complete,
                result=ReadJobResult(succeeded=1),
            )
        ]
        registry = HandlerRegistry()
        registry.register(
            JobType.ingest_validated_claims.value,
            handler,
            payload_models={1: IngestValidatedClaimsPayload},
        )
        job_id = await _enqueue_async(pg_session_factory, idempotency_key="shutdown-ac")

        worker = Worker(
            session_factory=pg_session_factory,
            handler_registry=registry,
        )

        claim_finished = asyncio.Event()
        claimed_ids = []
        release_calls = []
        post_claim_commits = 0
        original_claim_jobs = JobRepository.claim_jobs
        original_release = JobRepository.release_unstarted_job

        async def track_real_claim(
            repository,
            *,
            owner,
            batch_size,
            lease_duration_seconds,
        ):
            result = await original_claim_jobs(
                repository,
                owner=owner,
                batch_size=batch_size,
                lease_duration_seconds=lease_duration_seconds,
            )
            claimed_ids.extend(job.id for job in result)
            claim_finished.set()
            return result

        async def track_release(repository, *, job_id, owner, lease_token):
            released = await original_release(
                repository,
                job_id=job_id,
                owner=owner,
                lease_token=lease_token,
            )
            release_calls.append((job_id, released))
            return released

        original_commit = AsyncSession.commit

        async def commit_then_stop(session):
            nonlocal post_claim_commits
            await original_commit(session)
            if claim_finished.is_set():
                post_claim_commits += 1
                if post_claim_commits == 1:
                    worker.stop()

        caplog.set_level(logging.INFO, logger="app.jobs.worker")
        with (
            patch.object(JobRepository, "claim_jobs", track_real_claim),
            patch.object(JobRepository, "release_unstarted_job", track_release),
            patch.object(AsyncSession, "commit", commit_then_stop),
        ):
            task = asyncio.create_task(worker.start())
            await task

        row = await _job_status(pg_session_factory, job_id)
        assert claimed_ids == [job_id]
        assert release_calls == [(job_id, True)]
        assert post_claim_commits == 2
        assert row["status"] == JobStatus.pending.value
        assert row["attempt_count"] == 0
        assert row["lease_owner"] is None
        assert row["lease_token"] is None
        assert row["lease_expires_at"] is None
        assert handler.calls == []
        assert worker.active_executions() == []
        assert worker._handler_tasks == {}
        assert worker._renewal_tasks == {}
        assert not any(
            record.message == "worker_poll_failed" for record in caplog.records
        )


class TestWorkerShutdown:
    async def test_cancellation_cleanup_is_bounded_and_leaves_job_recoverable(
        self, pg_session_factory, monkeypatch, caplog
    ):
        import logging

        monkeypatch.setenv("JOBS_SHUTDOWN_DRAIN_SECONDS", "0.05")
        from app.core.settings import get_settings

        get_settings.cache_clear()

        class _SlowCancellationHandler(JobHandler):
            def __init__(self) -> None:
                self.started = asyncio.Event()
                self.cancelled = asyncio.Event()
                self.release_cleanup = asyncio.Event()

            async def handle(self, *, payload, attempt_count, max_attempts):
                self.started.set()
                try:
                    await asyncio.sleep(60)
                except asyncio.CancelledError:
                    self.cancelled.set()
                    await self.release_cleanup.wait()
                    raise

        handler = _SlowCancellationHandler()
        registry = HandlerRegistry()
        registry.register(
            JobType.ingest_validated_claims.value,
            handler,
            payload_models={1: IngestValidatedClaimsPayload},
        )
        job_id = await _enqueue_async(pg_session_factory, idempotency_key="slow-cancellation")
        worker = Worker(
            session_factory=pg_session_factory,
            handler_registry=registry,
            settings=get_settings(),
        )
        caplog.set_level(logging.INFO, logger="app.jobs.worker")
        worker_task = asyncio.create_task(worker.start())
        await asyncio.wait_for(handler.started.wait(), timeout=3)

        start = time.monotonic()
        worker.stop()
        await asyncio.wait_for(worker_task, timeout=2)
        elapsed = time.monotonic() - start

        row = await _job_status(pg_session_factory, job_id)
        assert elapsed < 1.5
        assert handler.cancelled.is_set()
        assert row["status"] == JobStatus.processing.value
        assert row["last_error"] is None
        assert any(
            record.message == "worker_cancellation_cleanup_timeout"
            for record in caplog.records
        )

        lingering = worker._handler_tasks[str(job_id)]
        handler.release_cleanup.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(lingering, timeout=1)

    async def test_module_entrypoint_handles_sigterm_cleanly(self):
        backend_root = __import__("pathlib").Path(__file__).resolve().parents[2]
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind(("127.0.0.1", 0))
            metrics_port = listener.getsockname()[1]
        worker_env = {
            **os.environ,
            "DATABASE_URL": os.environ.get(
                "TEST_DATABASE_URL",
                "postgresql+asyncpg://fotosintesis:fotosintesis@localhost:5432/fotosintesis",
            ),
            "JOBS_WORKER_ENABLED": "false",
            "JOBS_POLL_INTERVAL_SECONDS": "0.05",
            "JOBS_SHUTDOWN_DRAIN_SECONDS": "1",
            "JOBS_METRICS_HOST": "127.0.0.1",
            "JOBS_METRICS_PORT": str(metrics_port),
        }
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "app.jobs.worker",
            cwd=backend_root,
            env=worker_env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        assert process.stdout is not None
        output = ""
        try:
            async with asyncio.timeout(10):
                while "worker_signal_handlers_registered" not in output:
                    output += (await process.stdout.readline()).decode()
            process.send_signal(signal.SIGTERM)
            return_code = await asyncio.wait_for(process.wait(), timeout=5)
            output += (await process.stdout.read()).decode()
        finally:
            if process.returncode is None:
                process.kill()
                await process.wait()

        assert return_code == 0
        assert "worker_signal_handlers_registered" in output
        assert "worker_draining" in output
        assert "worker_stopped" in output
        assert "Traceback" not in output

    async def test_external_cancellation_propagates_after_cleanup(
        self, pg_session_factory
    ):
        worker = Worker(
            session_factory=pg_session_factory,
            handler_registry=HandlerRegistry(),
        )
        task = asyncio.create_task(worker.start())
        async with asyncio.timeout(3.0):
            await worker._ready_event.wait()

        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        assert worker._metrics_server is None
        assert worker.active_executions() == []
        assert worker._handler_tasks == {}
        assert worker._renewal_tasks == {}

    async def test_handler_completes_during_short_drain_without_new_claims(
        self, pg_session_factory, monkeypatch
    ):
        monkeypatch.setenv("JOBS_WORKER_CONCURRENCY", "1")
        monkeypatch.setenv("JOBS_LEASE_DURATION_SECONDS", "0.5")
        monkeypatch.setenv("JOBS_LEASE_RENEWAL_INTERVAL_SECONDS", "0.1")
        monkeypatch.setenv("JOBS_SHUTDOWN_DRAIN_SECONDS", "1")
        from app.core.settings import get_settings

        get_settings.cache_clear()
        started = asyncio.Event()
        release = asyncio.Event()

        class _DrainHandler(JobHandler):
            def payload_model(self, payload_version: int):
                return IngestValidatedClaimsPayload

            async def handle(self, *, payload, attempt_count, max_attempts):
                started.set()
                await release.wait()
                return JobHandlerResult(
                    status=JobStatus.complete,
                    result=ReadJobResult(succeeded=1),
                )

        registry = HandlerRegistry()
        registry.register(
            JobType.ingest_validated_claims.value,
            _DrainHandler(),
            payload_models={1: IngestValidatedClaimsPayload},
        )
        first_job = await _enqueue_async(pg_session_factory, idempotency_key="short-drain-1")
        worker = Worker(session_factory=pg_session_factory, handler_registry=registry)
        task = asyncio.create_task(worker.start())
        await asyncio.wait_for(started.wait(), timeout=3.0)
        initial_expiry = (await _job_status(pg_session_factory, first_job))["lease_expires_at"]
        second_job = await _enqueue_async(
            pg_session_factory, idempotency_key="short-drain-2"
        )

        worker.stop()
        await asyncio.sleep(0.2)
        renewed_expiry = (await _job_status(pg_session_factory, first_job))["lease_expires_at"]
        release.set()
        await asyncio.wait_for(task, timeout=3.0)

        assert (await _job_status(pg_session_factory, first_job))["status"] == "complete"
        assert (await _job_status(pg_session_factory, second_job))["status"] == "pending"
        assert renewed_expiry > initial_expiry
        assert worker.active_executions() == []
        assert worker._handler_tasks == {}
        assert worker._renewal_tasks == {}

    async def test_drain_timeout_leaves_recoverable_state(
        self, pg_session_factory, monkeypatch, caplog
    ):
        import logging

        from app.observability.metrics import MetricsRegistry

        monkeypatch.setenv("JOBS_LEASE_DURATION_SECONDS", "0.6")
        monkeypatch.setenv("JOBS_LEASE_RENEWAL_INTERVAL_SECONDS", "0.1")
        monkeypatch.setenv("JOBS_SHUTDOWN_DRAIN_SECONDS", "0.25")
        monkeypatch.setenv("JOBS_BACKOFF_BASE_SECONDS", "0.01")
        monkeypatch.setenv("JOBS_BACKOFF_CAP_SECONDS", "0.01")
        from app.core.settings import get_settings

        get_settings.cache_clear()
        cancelled = asyncio.Event()

        # Handler blocks indefinitely; drain timeout must release the
        # claim without writing `failed` so a future worker can recover.
        class _BlockingHandler(JobHandler):
            def payload_model(self, payload_version: int):
                return IngestValidatedClaimsPayload

            async def handle(self, *, payload, attempt_count, max_attempts):
                try:
                    await asyncio.sleep(60)
                except asyncio.CancelledError:
                    cancelled.set()
                    raise
                return JobHandlerResult(
                    status=JobStatus.complete,
                    result=ReadJobResult(succeeded=1),
                )

        registry = HandlerRegistry()
        registry.register(
            JobType.ingest_validated_claims.value,
            _BlockingHandler(),
            payload_models={1: IngestValidatedClaimsPayload},
        )
        metrics = MetricsRegistry()
        worker = Worker(
            session_factory=pg_session_factory,
            handler_registry=registry,
            metrics=metrics,
        )
        job_id = await _enqueue_async(pg_session_factory, idempotency_key="drain-test")

        caplog.set_level(logging.INFO, logger="app.jobs.worker")
        task = asyncio.create_task(worker.start())
        # Wait for the worker to claim the job.
        for _ in range(60):
            row = await _job_status(pg_session_factory, job_id)
            if row.get("status") == JobStatus.processing.value:
                break
            await asyncio.sleep(0.05)
        else:
            worker.stop()
            await task
            pytest.fail("worker did not claim the job")

        initial_expiry = (await _job_status(pg_session_factory, job_id))["lease_expires_at"]
        worker.stop()
        await asyncio.wait_for(task, timeout=10.0)

        row = await _job_status(pg_session_factory, job_id)
        # Status is still processing (handler was cancelled, not failed).
        assert row["status"] == JobStatus.processing.value
        # last_error must not be set; cancellation must not write failed.
        assert not row.get("last_error") or row["last_error"] is None
        assert row["lease_expires_at"] > initial_expiry
        assert cancelled.is_set()
        assert worker.active_executions() == []
        assert worker._handler_tasks == {}
        assert worker._renewal_tasks == {}
        assert metrics.job_outcomes[
            (JobType.ingest_validated_claims.value, "cancelled")
        ] == 1
        histogram = metrics.job_duration_histograms[
            (JobType.ingest_validated_claims.value, "cancelled")
        ]
        assert histogram.total_count == 1
        assert histogram.total_sum >= 0
        messages = {record.message for record in caplog.records}
        assert "worker_handler_cancelled" in messages
        assert "worker_drain_timeout" in messages
        rendered_logs = " ".join(str(record.__dict__) for record in caplog.records)
        for sentinel in (
            "https://secret.example/private-path",
            "Secretus plantus",
            "SECRET_CLAIM_TEXT",
            "SECRET_EVIDENCE_QUOTE",
            "22222222-2222-2222-2222-222222222222",
            "SECRET_LEASE_TOKEN",
        ):
            assert sentinel not in rendered_logs

        lease_wait = max(
            0.0,
            (row["lease_expires_at"] - datetime.now(timezone.utc)).total_seconds(),
        )
        await asyncio.sleep(lease_wait + 0.05)
        _FakeHandler._SCRIPT = [
            lambda _h: JobHandlerResult(
                status=JobStatus.complete,
                result=ReadJobResult(succeeded=1),
            )
        ]
        completing_handler = _FakeHandler()
        completing_registry = HandlerRegistry()
        completing_registry.register(
            JobType.ingest_validated_claims.value,
            completing_handler,
            payload_models={1: IngestValidatedClaimsPayload},
        )
        recovery_worker = Worker(
            session_factory=pg_session_factory,
            handler_registry=completing_registry,
        )
        recovery_task = asyncio.create_task(recovery_worker.start())
        for _ in range(80):
            recovered_row = await _job_status(pg_session_factory, job_id)
            if recovered_row["status"] == JobStatus.complete.value:
                break
            await asyncio.sleep(0.05)
        recovery_worker.stop()
        await recovery_task

        recovered_row = await _job_status(pg_session_factory, job_id)
        assert recovered_row["status"] == JobStatus.complete.value
        assert recovered_row["attempt_count"] == 2
        assert len(completing_handler.calls) == 1
