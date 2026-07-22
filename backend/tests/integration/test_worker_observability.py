"""Tests for the bounded worker observability surface.

Phase 7 requires:
- The histogram is bounded regardless of observation count.
- All required lifecycle events are emitted.
- ``caplog`` never contains sensitive content (payload, claim, quote, URL,
  scientific name, user id, conversation id, token, raw exception text).
- Prometheus labels are limited to closed enums.
- The worker metrics endpoint serves the worker registry output.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.auth.tables import application_jobs, users

pytestmark = [
    pytest.mark.skipif(
        "SKIP_PG_TESTS" in __import__("os").environ,
        reason="PostgreSQL not available (SKIP_PG_TESTS is set)",
    ),
]


@pytest.fixture(autouse=True)
def _worker_settings(monkeypatch):
    monkeypatch.setenv("JOBS_WORKER_ENABLED", "true")
    monkeypatch.setenv("JOBS_PRODUCER_ENABLED", "false")
    monkeypatch.setenv("JOBS_POLL_INTERVAL_SECONDS", "0.1")
    monkeypatch.setenv("JOBS_METRICS_PORT", "0")
    from app.core.settings import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _valid_payload(*, topic: str = "watering") -> dict:
    return {
        "claims": [
            {
                "scientific_name": "Secretus plantus",
                "topic": topic,
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


async def _wait_for_state(predicate, *, timeout: float = 3.0) -> None:
    async with asyncio.timeout(timeout):
        while not predicate():
            await asyncio.sleep(0.02)


async def _request_worker(worker, path: str = "/ready") -> str:
    assert worker._metrics_server is not None
    host, port = worker._metrics_server.sockets[0].getsockname()[:2]
    if host == "0.0.0.0":
        host = "127.0.0.1"
    reader, writer = await asyncio.open_connection(host=host, port=port)
    writer.write(f"GET {path} HTTP/1.1\r\nHost: localhost\r\n\r\n".encode())
    await writer.drain()
    response = await reader.read(8192)
    writer.close()
    await writer.wait_closed()
    return response.decode("utf-8")


def test_histogram_memory_is_bounded() -> None:
    from app.observability.metrics import Histogram, JOB_DURATION_BUCKETS

    histogram = Histogram()
    initial = sum(histogram.counts)  # +Inf bucket is included in counts

    samples = [0.05, 0.4, 1.5, 12.0, 90.0, 9999.0]
    for value in samples:
        histogram.observe(value)

    final = sum(histogram.counts)
    assert final - initial == len(samples)
    assert histogram.total_count == len(samples)
    assert histogram.total_sum == pytest.approx(sum(samples))
    # The bucket structure is fixed regardless of samples: buckets + +Inf.
    assert len(histogram.counts) == len(JOB_DURATION_BUCKETS) + 1

    rendered = histogram.render(
        name="duration_seconds",
        label_pairs=(("job_type", "ingest_validated_claims"),),
    )
    assert 'duration_seconds_bucket{job_type="ingest_validated_claims",le="0.5"} 2' in rendered
    assert 'duration_seconds_count{job_type="ingest_validated_claims"} 6' in rendered
    assert 'duration_seconds_sum{job_type="ingest_validated_claims"}' in rendered


def test_metrics_registry_renders_required_families() -> None:
    from app.observability.metrics import MetricsRegistry

    registry = MetricsRegistry()
    registry.record_job_claim(job_type="ingest_validated_claims")
    registry.record_job_outcome(
        job_type="ingest_validated_claims",
        status="complete",
        duration_seconds=0.42,
    )
    registry.record_job_outcome(
        job_type="ingest_validated_claims",
        status="failed",
        duration_seconds=1.5,
    )
    registry.record_job_outcome(
        job_type="ingest_validated_claims",
        status="lease_lost",
        duration_seconds=0.2,
    )
    registry.record_job_outcome(
        job_type="ingest_validated_claims",
        status="cancelled",
        duration_seconds=0.3,
    )
    registry.record_job_retry(
        job_type="ingest_validated_claims", category="provider_transient",
    )
    registry.record_job_stale_recovery(
        job_type="ingest_validated_claims", outcome="lease_expired",
    )
    registry.record_job_backlog(
        job_type="ingest_validated_claims", status="pending", count=7,
    )
    registry.record_oldest_eligible_age(age_seconds=12.5)
    registry.record_worker_successful_poll(timestamp_seconds=123.5)

    text = registry.to_prometheus()
    assert "fotosintesis_job_claims_total" in text
    assert 'job_type="ingest_validated_claims"' in text
    assert "fotosintesis_job_outcomes_total" in text
    assert "fotosintesis_job_retries_total" in text
    assert "fotosintesis_job_stale_recoveries_total" in text
    assert "fotosintesis_job_backlog_count" in text
    assert "fotosintesis_job_oldest_eligible_age_seconds" in text
    assert "fotosintesis_worker_last_successful_poll_timestamp_seconds 123.500000" in text
    assert "fotosintesis_job_attempt_duration_seconds" in text
    assert 'status="lease_lost"' in text
    assert 'status="cancelled"' in text
    assert text.count("# HELP fotosintesis_job_attempt_duration_seconds ") == 1
    assert text.count("# TYPE fotosintesis_job_attempt_duration_seconds histogram") == 1
    assert (
        'fotosintesis_job_attempt_duration_seconds_count{job_type="ingest_validated_claims",status="complete"} 1'
        in text
    )
    assert (
        'fotosintesis_job_attempt_duration_seconds_sum{job_type="ingest_validated_claims",status="failed"} 1.500000'
        in text
    )
    # No raw user/conversation/URL values should appear.
    for forbidden in ("user_id", "conversation_id", "http://"):
        assert forbidden not in text


def test_metrics_registry_rejects_unbounded_labels() -> None:
    from app.observability.metrics import MetricsRegistry

    registry = MetricsRegistry()
    with pytest.raises(ValueError):
        registry.record_job_claim(job_type="https://sensitive.example/job/123")
    with pytest.raises(ValueError):
        registry.record_job_outcome(
            job_type="ingest_validated_claims",
            status="user-controlled-status",
            duration_seconds=1,
        )
    with pytest.raises(ValueError):
        registry.record_job_retry(
            job_type="ingest_validated_claims",
            category="raw provider exception",
        )
    with pytest.raises(ValueError):
        registry.record_job_backlog(
            job_type="ingest_validated_claims",
            status="complete",
            count=1,
        )
    assert registry.job_claims_total == 0
    assert registry.job_outcomes == {}
    assert registry.job_retries_by_type_category == {}
    assert registry.job_backlog_by_type_status == {}


def test_backlog_snapshot_removes_absent_series() -> None:
    from app.observability.metrics import MetricsRegistry

    registry = MetricsRegistry()
    registry.record_job_backlog(
        job_type="ingest_validated_claims", status="pending", count=2
    )
    registry.reset_job_backlog()
    assert "fotosintesis_job_backlog_count{" not in registry.to_prometheus()


async def _setup_processing_job(pg_session_factory, *, lease_seconds: float = 300.0):
    from sqlalchemy import text as sa_text

    from app.auth.tables import application_jobs
    from app.jobs.repository import JobRepository
    from app.jobs.schemas import JobType

    job_id = None
    async with pg_session_factory() as s:
        repo = JobRepository(s)
        job_id = await repo.enqueue(
            job_type=JobType.ingest_validated_claims.value,
            payload_version=1,
            payload=_valid_payload(),
            idempotency_key=f"obs-{uuid4()}",
        )
        await s.commit()

    async with pg_session_factory() as s:
        await s.execute(
            sa_text(
                """
                UPDATE application_jobs
                SET status = 'processing',
                    lease_owner = 'w1',
                    lease_token = :token,
                    lease_expires_at = :expires
                WHERE id = :id
                """
            ),
            {
                "token": "SECRET_LEASE_TOKEN",
                "expires": datetime.now(timezone.utc) + timedelta(seconds=lease_seconds),
                "id": job_id,
            },
        )
        await s.commit()
    return job_id


class TestEventInventory:
    async def test_stale_recovery_event_emitted(self, pg_session_factory, caplog):
        from app.observability.metrics import metrics_registry

        caplog.set_level(logging.INFO, logger="app.jobs.worker")
        await _setup_processing_job(pg_session_factory, lease_seconds=-10)

        # Run a single reconcile tick.
        from app.jobs.worker import Worker
        from app.core.settings import get_settings

        settings = get_settings()
        worker = Worker(
            session_factory=pg_session_factory,
            settings=settings,
            metrics=metrics_registry,
            metrics_server_factory=lambda **_kwargs: asyncio.sleep(0, result=None),
        )
        await worker._reconcile()

        text = metrics_registry.to_prometheus()
        assert "fotosintesis_job_stale_recoveries_total" in text
        assert 'outcome="lease_expired"' in text
        # The structured log event is in the worker's logger.
        assert any(
            record.message == "job_stale_recovered"
            for record in caplog.records
        ), caplog.records
        assert_sensitive_values_absent(caplog.records)

    async def test_direct_expired_claim_emits_recovery_event_and_metric(
        self, pg_session_factory, caplog
    ):
        from app.jobs.handler import HandlerRegistry, JobHandler, JobHandlerResult
        from app.jobs.schemas import (
            IngestValidatedClaimsPayload,
            JobStatus,
            JobType,
            ReadJobResult,
        )
        from app.jobs.worker import Worker
        from app.observability.metrics import MetricsRegistry

        class _CompletingHandler(JobHandler):
            def payload_model(self, payload_version: int):
                return IngestValidatedClaimsPayload

            async def handle(self, *, payload, attempt_count, max_attempts):
                return JobHandlerResult(
                    status=JobStatus.complete,
                    result=ReadJobResult(succeeded=1),
                )

        job_id = await _setup_processing_job(pg_session_factory, lease_seconds=-30)
        registry = HandlerRegistry()
        registry.register(
            JobType.ingest_validated_claims.value,
            _CompletingHandler(),
            payload_models={1: IngestValidatedClaimsPayload},
        )
        metrics = MetricsRegistry()
        worker = Worker(
            session_factory=pg_session_factory,
            handler_registry=registry,
            metrics=metrics,
        )
        caplog.set_level(logging.INFO, logger="app.jobs.worker")

        assert await worker._claim(owner=worker.owner, batch_size=1) == 1
        async with asyncio.timeout(3.0):
            while worker._handler_tasks:
                await asyncio.sleep(0.02)

        assert metrics.job_stale_recoveries_by_type[
            (JobType.ingest_validated_claims.value, "lease_expired")
        ] == 1
        recovery = next(
            record for record in caplog.records if record.message == "job_stale_recovered"
        )
        assert recovery.message == "job_stale_recovered"
        assert recovery.__dict__["ctx_recovery_outcome"] == "lease_expired"
        assert recovery.__dict__["ctx_recovery_count"] == 1
        assert_sensitive_values_absent(caplog.records)
        async with pg_session_factory() as session:
            status = await session.scalar(
                select(application_jobs.c.status).where(application_jobs.c.id == job_id)
            )
        assert status == JobStatus.complete.value

    async def test_runtime_attempt_events_are_complete_and_payload_safe(
        self, pg_session_factory, caplog
    ):
        from app.jobs.handler import HandlerRegistry, JobHandler, JobHandlerResult
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

        class _OutcomeHandler(JobHandler):
            def payload_model(self, payload_version: int):
                return IngestValidatedClaimsPayload

            async def handle(self, *, payload, attempt_count, max_attempts):
                topic = payload.claims[0].topic
                if topic == "complete":
                    return JobHandlerResult(
                        status=JobStatus.complete,
                        result=ReadJobResult(succeeded=1),
                    )
                if topic == "partial":
                    return JobHandlerResult(
                        status=JobStatus.partial,
                        result=ReadJobResult(
                            succeeded=1,
                            failed=1,
                            partial=True,
                            limitations=[JobLimitation.some_claims_failed],
                        ),
                    )
                return JobHandlerResult.failed(
                    category=(
                        JobFailureCategory.provider_transient
                        if topic == "retry"
                        else JobFailureCategory.invariant_violation
                    ),
                    retryable=topic == "retry",
                )

        registry = HandlerRegistry()
        registry.register(
            JobType.ingest_validated_claims.value,
            _OutcomeHandler(),
            payload_models={1: IngestValidatedClaimsPayload},
        )
        job_ids = {}
        async with pg_session_factory() as session:
            repository = JobRepository(session)
            for topic in ("complete", "partial", "retry", "failed"):
                job_ids[topic] = await repository.enqueue(
                    job_type=JobType.ingest_validated_claims.value,
                    payload_version=1,
                    payload=_valid_payload(topic=topic),
                    idempotency_key=f"events-{topic}",
                )
            await session.commit()

        caplog.set_level(logging.INFO, logger="app.jobs.worker")
        worker = Worker(session_factory=pg_session_factory, handler_registry=registry)
        task = asyncio.create_task(worker.start())
        async with asyncio.timeout(3.0):
            while True:
                async with pg_session_factory() as session:
                    status_rows = await session.execute(
                        select(
                            application_jobs.c.id,
                            application_jobs.c.status,
                        ).where(application_jobs.c.id.in_(job_ids.values()))
                    )
                    rows = {row.id: row.status for row in status_rows}
                if (
                    rows[job_ids["complete"]] == "complete"
                    and rows[job_ids["partial"]] == "partial"
                    and rows[job_ids["retry"]] == "pending"
                    and rows[job_ids["failed"]] == "failed"
                ):
                    break
                await asyncio.sleep(0.02)
        worker.stop()
        await task

        records = {record.message: record for record in caplog.records}
        for event, outcome in (
            ("job_completed", "complete"),
            ("job_partial", "partial"),
            ("job_retry_scheduled", "retry_scheduled"),
            ("job_failed", "failed"),
        ):
            assert event in records
            record = records[event]
            assert record.__dict__["ctx_job_type"] == "ingest_validated_claims"
            assert record.__dict__["ctx_attempt"] == 1
            assert record.__dict__["ctx_duration"] >= 0
            assert record.__dict__["ctx_outcome"] == outcome
            assert record.__dict__["ctx_worker_identity"] == worker.owner
        assert records["job_completed"].__dict__["ctx_job_id"] == str(
            job_ids["complete"]
        )
        assert records["job_partial"].__dict__["ctx_job_id"] == str(job_ids["partial"])
        assert records["job_retry_scheduled"].__dict__["ctx_job_id"] == str(
            job_ids["retry"]
        )
        assert records["job_failed"].__dict__["ctx_job_id"] == str(job_ids["failed"])
        assert records["job_partial"].__dict__["ctx_limitations"] == [
            "some_claims_failed"
        ]
        assert records["job_retry_scheduled"].__dict__["ctx_failure_category"] == (
            "provider_transient"
        )
        assert records["job_retry_scheduled"].__dict__["ctx_retry_delay_seconds"] >= 0
        assert records["job_failed"].__dict__["ctx_failure_category"] == (
            "invariant_violation"
        )
        messages = {record.message for record in caplog.records}
        assert {"job_claimed", "worker_draining", "worker_stopped"} <= messages
        assert_sensitive_values_absent(caplog.records)
        rendered_logs = " ".join(str(record.__dict__) for record in caplog.records)
        for sentinel in (
            "SECRET_CLAIM_TEXT",
            "SECRET_EVIDENCE_QUOTE",
            "https://secret.example/private-path",
            "Secretus plantus",
        ):
            assert sentinel not in rendered_logs
        metrics_text = worker._metrics.to_prometheus()
        for job_id in job_ids.values():
            assert str(job_id) not in metrics_text


class TestTelemetrySafety:
    async def test_prometheus_labels_are_closed(self, pg_session_factory, test_user):
        from app.observability.metrics import metrics_registry

        async with pg_session_factory() as s:
            from app.jobs.repository import JobRepository
            repo = JobRepository(s)
            await repo.enqueue(
                job_type="ingest_validated_claims",
                payload_version=1,
                payload=_valid_payload(),
                idempotency_key=f"label-{uuid4()}",
                user_id=test_user,
            )
            await s.commit()
        # Record a few outcomes with arbitrary values; the renderer must
        # never include user-provided content.
        metrics_registry.record_job_outcome(
            job_type="ingest_validated_claims",
            status="complete",
            duration_seconds=0.1,
        )
        text = metrics_registry.to_prometheus()
        # No user/URL/scientific name in the rendered output. The metric
        # name contains the substring "claim" (job_claims_total) so we
        # check the label values rather than the full text.
        for forbidden in (
            "user_id", "conversation_id", "scientific_name", "http://",
            "https://", "source_support_", "evidence_quote",
        ):
            assert forbidden not in text
        # Label values are drawn from closed enums plus numeric bucket boundaries.
        from app.jobs.schemas import JobFailureCategory

        closed_label_values = {
            "ingest_validated_claims",
            "pending", "processing", "complete", "partial", "failed", "retry_scheduled",
            "lease_lost", "cancelled",
            "lease_expired", "attempts_exhausted", "provider_transient", "created", "reused",
            "0", "1", "0.1", "0.5", "1.0", "2.5", "5.0", "10.0", "30.0", "60.0", "300.0", "+Inf",
        }
        closed_label_values.update(item.value for item in JobFailureCategory)
        import re
        for value in re.findall(r'"([^"]*)"', text):
            assert value in closed_label_values, value

    def test_lease_loss_and_cancellation_are_closed_outcomes(self):
        from app.observability.metrics import MetricsRegistry

        registry = MetricsRegistry()
        registry.record_job_outcome(
            job_type="ingest_validated_claims",
            status="lease_lost",
            duration_seconds=1.0,
        )
        registry.record_job_outcome(
            job_type="ingest_validated_claims",
            status="cancelled",
            duration_seconds=2.0,
        )
        rendered = registry.to_prometheus()
        assert 'status="lease_lost"' in rendered
        assert 'status="cancelled"' in rendered
        with pytest.raises(ValueError):
            registry.record_job_outcome(
                job_type="ingest_validated_claims",
                status="arbitrary",
                duration_seconds=1.0,
            )


class TestBacklogCollection:
    async def test_worker_status_metrics_include_every_lifecycle_state(
        self, pg_session_factory
    ):
        from app.jobs.handler import HandlerRegistry
        from app.jobs.repository import JobRepository
        from app.jobs.schemas import JobStatus, JobType
        from app.jobs.worker import Worker
        from app.observability.metrics import MetricsRegistry

        async with pg_session_factory() as session:
            repo = JobRepository(session)
            ids = {
                status: await repo.enqueue(
                    job_type=JobType.ingest_validated_claims.value,
                    payload_version=1,
                    payload=_valid_payload(topic=f"status-{status}"),
                    idempotency_key=f"status-count-{status}",
                )
                for status in JobStatus
            }
            await session.commit()
            await session.execute(
                application_jobs.update()
                .where(application_jobs.c.id == ids[JobStatus.processing])
                .values(
                    status=JobStatus.processing.value,
                    lease_owner="metrics-worker",
                    lease_token="metrics-token",
                    lease_expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
                )
            )
            for status in (JobStatus.complete, JobStatus.partial, JobStatus.failed):
                await session.execute(
                    application_jobs.update()
                    .where(application_jobs.c.id == ids[status])
                    .values(status=status.value, completed_at=datetime.now(timezone.utc))
                )
            await session.commit()

        metrics = MetricsRegistry()
        worker = Worker(
            session_factory=pg_session_factory,
            handler_registry=HandlerRegistry(),
            metrics=metrics,
        )
        await worker._refresh_backlog_metrics()
        output = metrics.to_prometheus()
        for status in JobStatus:
            assert (
                "fotosintesis_job_status_count{"
                f'job_type="ingest_validated_claims",status="{status.value}"}} 1'
            ) in output
        assert 'fotosintesis_job_backlog_count{job_type="ingest_validated_claims",status="complete"}' not in output

        async with pg_session_factory() as session:
            await session.execute(
                application_jobs.delete().where(
                    application_jobs.c.id.in_([
                        ids[JobStatus.complete],
                        ids[JobStatus.partial],
                        ids[JobStatus.failed],
                    ])
                )
            )
            await session.commit()
        await worker._refresh_backlog_metrics()
        refreshed = metrics.to_prometheus()
        for status in (JobStatus.complete, JobStatus.partial, JobStatus.failed):
            assert f'status="{status.value}"' not in refreshed

    async def test_worker_backlog_metrics_through_collector(
        self, pg_session_factory
    ):
        from app.jobs.handler import HandlerRegistry
        from app.jobs.repository import JobRepository
        from app.jobs.schemas import JobStatus, JobType
        from app.jobs.worker import Worker
        from app.observability.metrics import MetricsRegistry

        metrics = MetricsRegistry()

        # Create two eligible pending, one processing, one complete, and one
        # future pending job. Future work belongs in the pending count but not
        # in the oldest eligible age.
        async with pg_session_factory() as session:
            repo = JobRepository(session)
            pending_ids = []
            for i in range(2):
                jid = await repo.enqueue(
                    job_type=JobType.ingest_validated_claims.value,
                    payload_version=1,
                    payload=_valid_payload(topic="backlog"),
                    idempotency_key=f"bl-collect-{i}",
                )
                pending_ids.append(jid)
            future_id = await repo.enqueue(
                job_type=JobType.ingest_validated_claims.value,
                payload_version=1,
                payload=_valid_payload(topic="backlog-future"),
                idempotency_key="bl-collect-future",
                available_at=datetime.now(timezone.utc) + timedelta(hours=1),
            )
            await session.commit()

        processing_id = await _setup_processing_job(
            pg_session_factory, lease_seconds=300
        )

        async with pg_session_factory() as session:
            repo = JobRepository(session)
            jid = await repo.enqueue(
                job_type=JobType.ingest_validated_claims.value,
                payload_version=1,
                payload=_valid_payload(topic="backlog-complete"),
                idempotency_key="bl-collect-complete",
            )
            await session.commit()
            import sqlalchemy as sa
            await session.execute(
                sa.text("""
                    UPDATE application_jobs
                    SET status = 'complete', lease_owner = NULL,
                        lease_token = NULL, lease_expires_at = NULL,
                        completed_at = NOW()
                    WHERE id = :id
                """),
                {"id": jid},
            )
            await session.commit()

        worker = Worker(
            session_factory=pg_session_factory,
            handler_registry=HandlerRegistry(),
            metrics=metrics,
        )
        await worker._refresh_backlog_metrics()

        output = worker._metrics.to_prometheus()
        assert (
            'fotosintesis_job_backlog_count{'
            'job_type="ingest_validated_claims",status="pending"} 3'
        ) in output, output
        assert worker._metrics.job_oldest_eligible_age_seconds is not None
        assert worker._metrics.job_oldest_eligible_age_seconds > 0
        assert (
            'fotosintesis_job_backlog_count{'
            'job_type="ingest_validated_claims",status="processing"} 1'
        ) in output, output
        assert 'fotosintesis_job_backlog_count{job_type="ingest_validated_claims",status="complete"}' not in output, output

        # Leave only future work active. It belongs in the pending count but
        # cannot contribute to the currently eligible age.
        async with pg_session_factory() as session:
            import sqlalchemy as sa
            for jid in [*pending_ids, processing_id]:
                await session.execute(
                    sa.text(
                        """
                        UPDATE application_jobs
                        SET status = 'failed', lease_owner = NULL,
                            lease_token = NULL, lease_expires_at = NULL
                        WHERE id = :id
                        """
                    ),
                    {"id": jid},
                )
            await session.commit()

        await worker._refresh_backlog_metrics()
        output = worker._metrics.to_prometheus()
        assert (
            'fotosintesis_job_backlog_count{'
            'job_type="ingest_validated_claims",status="pending"} 1'
        ) in output, output
        assert worker._metrics.job_oldest_eligible_age_seconds in (None, 0)

        # After marking the future job terminal, stale active series disappear.
        async with pg_session_factory() as session:
            await session.execute(
                sa.text(
                    """
                    UPDATE application_jobs
                    SET status = 'failed', lease_owner = NULL,
                        lease_token = NULL, lease_expires_at = NULL
                    WHERE id = :id
                    """
                ),
                {"id": future_id},
            )
            await session.commit()

        await worker._refresh_backlog_metrics()
        output = worker._metrics.to_prometheus()
        assert "fotosintesis_job_backlog_count{" not in output
        assert worker._metrics.job_oldest_eligible_age_seconds in (None, 0)


SENSITIVE_VALUES = {
    "url": "https://secret.example/private-path",
    "scientific_name": "Secretus plantus",
    "claim": "SECRET_CLAIM_TEXT",
    "quote": "SECRET_EVIDENCE_QUOTE",
    "user_id": "11111111-1111-1111-1111-111111111111",
    "conversation_id": "22222222-2222-2222-2222-222222222222",
    "lease_token": "SECRET_LEASE_TOKEN",
    "credential": "sk-secret-provider-token",
    "exception": "SECRET_RAW_EXCEPTION",
}


def assert_sensitive_values_absent(records) -> None:
    assert records, "expected worker logs but captured none"
    rendered = "\n".join(
        f"{record.message} {record.__dict__}"
        for record in records
    )
    for value in SENSITIVE_VALUES.values():
        assert value not in rendered


class TestComprehensiveSensitiveLog:
    async def test_complete_path_emits_logs_without_sensitive_values(
        self, pg_session_factory, caplog, monkeypatch
    ):
        import logging
        from app.jobs.handler import HandlerRegistry, JobHandler, JobHandlerResult
        from app.jobs.repository import JobRepository
        from app.jobs.schemas import (
            IngestValidatedClaimsPayload,
            JobFailureCategory,
            JobStatus,
            JobType,
            ReadJobResult,
        )
        from app.jobs.worker import Worker

        class _SensitiveHandler(JobHandler):
            def payload_model(self, payload_version: int):
                return IngestValidatedClaimsPayload

            async def handle(self, *, payload, attempt_count, max_attempts):
                return JobHandlerResult(
                    status=JobStatus.complete,
                    result=ReadJobResult(succeeded=1),
                )

        handler = _SensitiveHandler()
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
        caplog.set_level(logging.INFO, logger="app.jobs.worker")

        sensitive_payload = _valid_payload(topic="sensitive")
        sensitive_payload["claims"][0]["scientific_name"] = "Secretus plantus"
        sensitive_payload["claims"][0]["claim"] = "SECRET_CLAIM_TEXT"
        sensitive_payload["claims"][0]["evidence_quote"] = "SECRET_EVIDENCE_QUOTE"
        sensitive_payload["claims"][0]["source_url"] = "https://secret.example/private-path"
        sensitive_payload["conversation_id"] = "22222222-2222-2222-2222-222222222222"

        task = asyncio.create_task(worker.start())
        await asyncio.sleep(0.2)

        async with pg_session_factory() as session:
            sensitive_user_id = UUID("11111111-1111-1111-1111-111111111111")
            await session.execute(
                users.insert().values(
                    id=sensitive_user_id,
                    name="Sensitive Test User",
                    email="11111111-1111-1111-1111-111111111111@test.invalid",
                    email_verified=True,
                )
            )
            job_id = await JobRepository(session).enqueue(
                job_type=JobType.ingest_validated_claims.value,
                payload_version=1,
                payload=sensitive_payload,
                idempotency_key=f"sensitive-{uuid4()}",
                user_id=sensitive_user_id,
            )
            await session.commit()

        for _ in range(60):
            async with pg_session_factory() as ns:
                row = (await ns.execute(
                    select(application_jobs.c.status).where(
                        application_jobs.c.id == job_id
                    )
                )).first()
            if row and row._mapping["status"] == "complete":
                break
            await asyncio.sleep(0.05)

        worker.stop()
        await asyncio.wait_for(task, timeout=3)

        assert any(record.message == "job_completed" for record in caplog.records)
        assert_sensitive_values_absent(caplog.records)


class TestWorkerMetricsEndpoint:
    async def test_endpoint_serves_registry(self, pg_session_factory):
        from app.jobs.metrics_server import start_metrics_server, stop_metrics_server
        from app.observability.metrics import metrics_registry

        metrics_registry.record_job_claim(job_type="ingest_validated_claims")
        metrics_registry.record_job_outcome(
            job_type="ingest_validated_claims",
            status="complete",
            duration_seconds=0.1,
        )

        server = await start_metrics_server(
            host="127.0.0.1",
            port=0,  # ephemeral
            render_prometheus=metrics_registry.to_prometheus,
        )
        assert server is not None
        try:
            host, port = server.sockets[0].getsockname()[:2]
            reader, writer = await asyncio.open_connection(host=host, port=port)
            writer.write(b"GET /metrics HTTP/1.1\r\nHost: localhost\r\n\r\n")
            await writer.drain()
            response = await reader.read(8192)
            writer.close()
            await writer.wait_closed()
        finally:
            await stop_metrics_server(server)

        body = response.decode("utf-8")
        assert body.startswith("HTTP/1.1 200 OK")
        assert "Content-Type: text/plain; version=0.0.4" in body
        body_text = body.split("\r\n\r\n", 1)[1]
        assert "fotosintesis_job_claims_total" in body_text
        assert "fotosintesis_job_outcomes_total" in body_text


class TestWorkerReadiness:
    async def test_local_runtime_uses_production_registry_and_postgresql_contracts(
        self, pg_session_factory, monkeypatch
    ):
        from app.core.settings import get_settings
        from app.jobs.handler import get_handler_registry
        from app.jobs.schemas import JobType
        from app.jobs.worker import Worker

        monkeypatch.setenv("JOBS_WORKER_ENABLED", "false")
        get_settings.cache_clear()
        worker = Worker(
            session_factory=pg_session_factory,
            settings=get_settings(),
        )

        task = asyncio.create_task(worker.start())
        await _wait_for_state(worker._ready_event.is_set)
        assert get_handler_registry().get_handler(
            JobType.ingest_validated_claims.value
        ) is not None
        assert (await _request_worker(worker)).startswith("HTTP/1.1 200 OK")
        worker.stop()
        await task

    async def test_invalid_embedding_provider_keeps_worker_unready(
        self, pg_session_factory, caplog
    ):
        from app.jobs.handler import HandlerRegistry
        from app.jobs.handlers.ingest_validated_claims import (
            IngestValidatedClaimsHandler,
        )
        from app.jobs.schemas import IngestValidatedClaimsPayload, JobType
        from app.jobs.worker import Worker

        sentinel = "sk-secret-provider-token"

        def invalid_registry():
            raise ValueError(sentinel)

        handler = IngestValidatedClaimsHandler(
            session_factory=pg_session_factory,
            provider_registry_factory=invalid_registry,
        )
        registry = HandlerRegistry()
        registry.register(
            JobType.ingest_validated_claims.value,
            handler,
            payload_models={1: IngestValidatedClaimsPayload},
        )
        worker = Worker(session_factory=pg_session_factory, handler_registry=registry)
        caplog.set_level(logging.INFO, logger="app.jobs.worker")

        task = asyncio.create_task(worker.start())
        await asyncio.sleep(0.25)
        assert not worker._ready_event.is_set()
        assert (await _request_worker(worker)).startswith(
            "HTTP/1.1 503 Service Unavailable"
        )
        worker.stop()
        await task

        assert any(
            record.message == "worker_dependency_validation_failed"
            and record.__dict__.get("ctx_failure_category") == "invariant_violation"
            for record in caplog.records
        )
        assert_sensitive_values_absent(caplog.records)
        assert sentinel not in " ".join(str(record.__dict__) for record in caplog.records)

    async def test_dependency_failure_prevents_claims_and_preserves_pending_job(
        self, pg_session_factory, caplog
    ):
        from app.jobs.handler import HandlerRegistry
        from app.jobs.handlers.ingest_validated_claims import (
            IngestValidatedClaimsHandler,
        )
        from app.jobs.repository import JobRepository
        from app.jobs.schemas import IngestValidatedClaimsPayload, JobStatus, JobType
        from app.jobs.worker import Worker
        from app.observability.metrics import MetricsRegistry

        sentinel = "SECRET_PROVIDER_REGISTRY_FAILURE"

        def invalid_registry():
            raise ValueError(sentinel)

        class TrackingHandler(IngestValidatedClaimsHandler):
            def __init__(self):
                super().__init__(
                    session_factory=pg_session_factory,
                    provider_registry_factory=invalid_registry,
                )
                self.calls = []

            async def handle(self, **kwargs):
                self.calls.append(kwargs)
                return await super().handle(**kwargs)

        handler = TrackingHandler()
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
                idempotency_key=f"dependency-failure-{uuid4()}",
            )
            await session.commit()

        metrics = MetricsRegistry()
        worker = Worker(
            session_factory=pg_session_factory,
            handler_registry=registry,
            metrics=metrics,
        )
        caplog.set_level(logging.INFO, logger="app.jobs.worker")
        task = asyncio.create_task(worker.start())
        key = (JobType.ingest_validated_claims.value, JobStatus.pending.value)
        await _wait_for_state(lambda: metrics.job_backlog_by_type_status.get(key) == 1)
        assert not worker._ready_event.is_set()
        assert (await _request_worker(worker)).startswith(
            "HTTP/1.1 503 Service Unavailable"
        )
        worker.stop()
        await task

        async with pg_session_factory() as session:
            row = (
                await session.execute(
                    select(
                        application_jobs.c.status,
                        application_jobs.c.attempt_count,
                    ).where(application_jobs.c.id == job_id)
                )
            ).mappings().one()
        assert row["status"] == JobStatus.pending.value
        assert row["attempt_count"] == 0
        assert handler.calls == []
        assert metrics.job_backlog_by_type_status[key] == 1
        assert metrics.job_status_by_type[key] == 1
        assert metrics.job_oldest_eligible_age_seconds is not None
        assert metrics.job_oldest_eligible_age_seconds >= 0
        assert metrics.worker_last_successful_poll_timestamp_seconds is None
        assert metrics.job_claims_total == 0
        assert any(
            record.message == "worker_dependency_validation_failed"
            for record in caplog.records
        )
        assert_sensitive_values_absent(caplog.records)
        assert sentinel not in " ".join(str(record.__dict__) for record in caplog.records)

    async def test_missing_embedding_credential_keeps_worker_unready(
        self, pg_session_factory, monkeypatch
    ):
        from app.core.settings import get_settings
        from app.jobs.handler import HandlerRegistry
        from app.jobs.handlers.ingest_validated_claims import (
            IngestValidatedClaimsHandler,
        )
        from app.jobs.schemas import IngestValidatedClaimsPayload, JobType
        from app.jobs.worker import Worker

        monkeypatch.setenv("EMBEDDING_PROVIDER", "openai")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        get_settings.cache_clear()
        registry = HandlerRegistry()
        registry.register(
            JobType.ingest_validated_claims.value,
            IngestValidatedClaimsHandler(
                session_factory=pg_session_factory,
                settings=get_settings(),
            ),
            payload_models={1: IngestValidatedClaimsPayload},
        )
        worker = Worker(
            session_factory=pg_session_factory,
            handler_registry=registry,
            settings=get_settings(),
        )

        task = asyncio.create_task(worker.start())
        await asyncio.sleep(0.25)
        assert not worker._ready_event.is_set()
        assert (await _request_worker(worker)).startswith(
            "HTTP/1.1 503 Service Unavailable"
        )
        worker.stop()
        await task

    async def test_valid_dependencies_and_reconciliation_set_readiness(
        self, pg_session_factory
    ):
        from app.jobs.handler import HandlerRegistry
        from app.jobs.handlers.ingest_validated_claims import (
            IngestValidatedClaimsHandler,
        )
        from app.jobs.schemas import IngestValidatedClaimsPayload, JobType
        from app.jobs.worker import Worker

        import types

        def valid_registry():
            return types.SimpleNamespace(embeddings=object())

        registry = HandlerRegistry()
        registry.register(
            JobType.ingest_validated_claims.value,
            IngestValidatedClaimsHandler(
                session_factory=pg_session_factory,
                provider_registry_factory=valid_registry,
            ),
            payload_models={1: IngestValidatedClaimsPayload},
        )
        worker = Worker(session_factory=pg_session_factory, handler_registry=registry)

        task = asyncio.create_task(worker.start())
        await _wait_for_state(worker._ready_event.is_set)
        assert (await _request_worker(worker)).startswith("HTTP/1.1 200 OK")
        worker.stop()
        await task

    async def test_reconciliation_failure_recovers_without_leaking_error(
        self, pg_session_factory, caplog
    ):
        from app.jobs.handler import HandlerRegistry, JobHandler, JobHandlerResult
        from app.jobs.repository import JobRepository
        from app.jobs.schemas import (
            IngestValidatedClaimsPayload,
            JobStatus,
            JobType,
            ReadJobResult,
        )
        from app.jobs.worker import Worker

        class _CompletingHandler(JobHandler):
            def payload_model(self, payload_version: int):
                return IngestValidatedClaimsPayload

            async def handle(self, *, payload, attempt_count, max_attempts):
                return JobHandlerResult(
                    status=JobStatus.complete,
                    result=ReadJobResult(succeeded=1),
                )

        registry = HandlerRegistry()
        registry.register(
            JobType.ingest_validated_claims.value,
            _CompletingHandler(),
            payload_models={1: IngestValidatedClaimsPayload},
        )
        async with pg_session_factory() as session:
            job_id = await JobRepository(session).enqueue(
                job_type=JobType.ingest_validated_claims.value,
                payload_version=1,
                payload=_valid_payload(),
                idempotency_key="poll-recovery",
            )
            await session.commit()
        worker = Worker(session_factory=pg_session_factory, handler_registry=registry)
        reconcile = worker._reconcile
        calls = 0

        async def flaky_reconcile() -> None:
            nonlocal calls
            calls += 1
            if calls == 1:
                raise RuntimeError("SECRET_RAW_EXCEPTION")
            await reconcile()

        worker._reconcile = flaky_reconcile
        caplog.set_level(logging.INFO, logger="app.jobs.worker")

        task = asyncio.create_task(worker.start())
        await asyncio.sleep(0.05)
        assert not worker._ready_event.is_set()
        assert (await _request_worker(worker)).startswith(
            "HTTP/1.1 503 Service Unavailable"
        )
        await _wait_for_state(worker._ready_event.is_set)
        assert (await _request_worker(worker)).startswith("HTTP/1.1 200 OK")
        async with asyncio.timeout(3.0):
            while True:
                async with pg_session_factory() as session:
                    status = await session.scalar(
                        select(application_jobs.c.status).where(
                            application_jobs.c.id == job_id
                        )
                    )
                if status == JobStatus.complete.value:
                    break
                await asyncio.sleep(0.02)
        worker.stop()
        await task

        assert calls >= 2
        poll_failures = [
            record for record in caplog.records if record.message == "worker_poll_failed"
        ]
        assert poll_failures
        assert poll_failures[0].__dict__["ctx_failure_category"] == "database_transient"
        assert_sensitive_values_absent(caplog.records)
        assert "SECRET_RAW_EXCEPTION" not in " ".join(
            str(record.__dict__) for record in caplog.records
        )

    async def test_disabled_worker_is_ready_without_claiming(
        self, pg_session_factory, monkeypatch
    ):
        from app.core.settings import get_settings
        from app.jobs.handler import HandlerRegistry
        from app.jobs.repository import JobRepository
        from app.jobs.schemas import JobStatus, JobType
        from app.jobs.worker import Worker
        from app.observability.metrics import MetricsRegistry

        monkeypatch.setenv("JOBS_WORKER_ENABLED", "false")
        get_settings.cache_clear()
        async with pg_session_factory() as session:
            job_id = await JobRepository(session).enqueue(
                job_type=JobType.ingest_validated_claims.value,
                payload_version=1,
                payload=_valid_payload(),
                idempotency_key="disabled-worker",
            )
            await session.commit()
        metrics = MetricsRegistry()
        worker = Worker(
            session_factory=pg_session_factory,
            handler_registry=HandlerRegistry(),
            settings=get_settings(),
            metrics=metrics,
        )
        worker._claim = AsyncMock()
        worker._reconcile = AsyncMock()

        task = asyncio.create_task(worker.start())
        await _wait_for_state(worker._ready_event.is_set)
        assert not task.done()
        assert (await _request_worker(worker)).startswith("HTTP/1.1 200 OK")
        await asyncio.sleep(0.15)
        async with pg_session_factory() as session:
            status = await session.scalar(
                select(application_jobs.c.status).where(application_jobs.c.id == job_id)
            )
        worker.stop()
        await task

        assert status == JobStatus.pending.value
        worker._claim.assert_not_awaited()
        worker._reconcile.assert_not_awaited()
        assert not worker._ready_event.is_set()
        key = (JobType.ingest_validated_claims.value, JobStatus.pending.value)
        assert metrics.job_backlog_by_type_status[key] == 1
        assert metrics.job_status_by_type[key] == 1
        assert metrics.job_oldest_eligible_age_seconds is not None
        assert metrics.job_oldest_eligible_age_seconds >= 0
        assert metrics.worker_last_successful_poll_timestamp_seconds is not None
        assert metrics.worker_last_successful_poll_timestamp_seconds > 0
        assert metrics.job_claims_total == 0

    async def test_disabled_worker_stays_unready_when_queue_query_fails(
        self, pg_session_factory, monkeypatch, caplog
    ):
        from app.core.settings import get_settings
        from app.jobs.handler import HandlerRegistry
        from app.jobs.repository import JobRepository
        from app.jobs.worker import Worker
        from app.observability.metrics import MetricsRegistry

        sentinel = "SECRET_QUEUE_SCHEMA_FAILURE"
        monkeypatch.setenv("JOBS_WORKER_ENABLED", "false")
        get_settings.cache_clear()

        async def fail_backlog_counts(_repository):
            raise RuntimeError(sentinel)

        monkeypatch.setattr(JobRepository, "get_backlog_counts", fail_backlog_counts)
        metrics = MetricsRegistry()
        worker = Worker(
            session_factory=pg_session_factory,
            handler_registry=HandlerRegistry(),
            settings=get_settings(),
            metrics=metrics,
        )
        worker._claim = AsyncMock()
        caplog.set_level(logging.INFO, logger="app.jobs.worker")

        task = asyncio.create_task(worker.start())
        try:
            await asyncio.sleep(0.2)
            assert not worker._ready_event.is_set()
            assert (await _request_worker(worker)).startswith(
                "HTTP/1.1 503 Service Unavailable"
            )
        finally:
            worker.stop()
            await task

        worker._claim.assert_not_awaited()
        assert metrics.worker_last_successful_poll_timestamp_seconds is None
        assert sentinel not in " ".join(str(record.__dict__) for record in caplog.records)

    async def test_disabled_worker_recovers_after_queue_query_failure(
        self, pg_session_factory, monkeypatch
    ):
        from app.core.settings import get_settings
        from app.jobs.handler import HandlerRegistry
        from app.jobs.repository import JobRepository
        from app.jobs.schemas import JobStatus, JobType
        from app.jobs.worker import Worker
        from app.observability.metrics import MetricsRegistry

        monkeypatch.setenv("JOBS_WORKER_ENABLED", "false")
        get_settings.cache_clear()
        async with pg_session_factory() as session:
            await JobRepository(session).enqueue(
                job_type=JobType.ingest_validated_claims.value,
                payload_version=1,
                payload=_valid_payload(),
                idempotency_key=f"disabled-recovery-{uuid4()}",
            )
            await session.commit()
        original_get_backlog_counts = JobRepository.get_backlog_counts
        calls = 0

        async def fail_once(repository):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise RuntimeError("SECRET_QUEUE_SCHEMA_FAILURE")
            return await original_get_backlog_counts(repository)

        monkeypatch.setattr(JobRepository, "get_backlog_counts", fail_once)
        metrics = MetricsRegistry()
        worker = Worker(
            session_factory=pg_session_factory,
            handler_registry=HandlerRegistry(),
            settings=get_settings(),
            metrics=metrics,
        )
        worker._claim = AsyncMock()

        task = asyncio.create_task(worker.start())
        try:
            await asyncio.sleep(0.05)
            assert not worker._ready_event.is_set()
            assert (await _request_worker(worker)).startswith(
                "HTTP/1.1 503 Service Unavailable"
            )
            await _wait_for_state(worker._ready_event.is_set)
            assert (await _request_worker(worker)).startswith("HTTP/1.1 200 OK")
            key = (JobType.ingest_validated_claims.value, JobStatus.pending.value)
            assert key in metrics.job_status_by_type
        finally:
            worker.stop()
            await task

        assert calls >= 2
        worker._claim.assert_not_awaited()
        assert metrics.worker_last_successful_poll_timestamp_seconds is not None

    async def test_readiness_requires_successful_reconciliation(self):
        from app.jobs.metrics_server import start_metrics_server, stop_metrics_server

        ready = False
        server = await start_metrics_server(
            host="127.0.0.1",
            port=0,
            render_prometheus=lambda: "metrics\n",
            is_ready=lambda: ready,
        )
        assert server is not None

        async def request() -> str:
            host, port = server.sockets[0].getsockname()[:2]
            reader, writer = await asyncio.open_connection(host=host, port=port)
            writer.write(b"GET /ready HTTP/1.1\r\nHost: localhost\r\n\r\n")
            await writer.drain()
            response = await reader.read(1024)
            writer.close()
            await writer.wait_closed()
            return response.decode("utf-8")

        try:
            assert (await request()).startswith("HTTP/1.1 503 Service Unavailable")
            ready = True
            assert (await request()).startswith("HTTP/1.1 200 OK")
        finally:
            await stop_metrics_server(server)
