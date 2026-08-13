from __future__ import annotations

import asyncio
import inspect
import logging
import os
import signal
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import text

from app.core.settings import Settings, get_settings
from app.db.session import AsyncSessionLocal
from app.enrichment.policy import enrichment_policy_label
from app.jobs.handler import (
    EnrichmentEfficacySnapshot,
    JobHandler,
    JobHandlerResult,
    PermanentJobError,
    RetryableJobError,
    get_handler_registry,
)
from app.jobs.handlers.register import get_production_payload_model, register_handlers
from app.jobs.metrics_server import start_metrics_server, stop_metrics_server
from app.jobs.repository import JobRepository
from app.jobs.schemas import (
    ClaimedJob,
    EnrichConfirmedPlantPayload,
    EnrichmentJobResult,
    JobError,
    JobFailureCategory,
    JobStatus,
    JobType,
    ReadJobResult,
)
from app.observability.logging import configure_logging
from app.observability.metrics import metrics_registry

logger = logging.getLogger(__name__)


TERMINAL_FAILURE_CATEGORIES: frozenset[JobFailureCategory] = frozenset(
    {
        JobFailureCategory.unsupported_payload_version,
        JobFailureCategory.invalid_payload,
        JobFailureCategory.unknown_job_type,
        JobFailureCategory.attempts_exhausted,
        JobFailureCategory.invariant_violation,
    }
)
CANCELLATION_CLEANUP_TIMEOUT_SECONDS = 1.0


def _is_retryable(failure_category: JobFailureCategory) -> bool:
    return failure_category not in TERMINAL_FAILURE_CATEGORIES


def _validate_required_contracts(*, get_payload_model, configured: str) -> None:
    for contract in filter(None, (item.strip() for item in configured.split(","))):
        job_type, separator, raw_version = contract.partition(":")
        if not separator or not raw_version.isdigit():
            raise RuntimeError("invalid required job contract configuration")
        if get_payload_model(job_type, int(raw_version)) is None:
            raise RuntimeError("required job contract is not registered")


def _validate_result_contract(result: JobHandlerResult) -> JobHandlerResult:
    details = result.result
    if isinstance(details, EnrichmentJobResult):
        valid = result.error is None and (
            result.status is JobStatus.complete
            and details.outcome == "complete"
            and not details.missing_aspects
            or result.status is JobStatus.partial
            and details.outcome == "partial"
            and bool(details.missing_aspects)
        )
        if valid:
            return result
        return JobHandlerResult.failed(
            category=JobFailureCategory.invariant_violation,
            retryable=False,
            efficacy=result.efficacy,
        )

    useful_count = (
        details.succeeded + details.skipped
        if isinstance(details, ReadJobResult)
        else 0
    )

    valid = False
    if result.status is JobStatus.complete:
        valid = (
            details is not None
            and result.error is None
            and useful_count > 0
            and isinstance(details, ReadJobResult)
            and details.failed == 0
            and not details.partial
            and not details.limitations
        )
    elif result.status is JobStatus.partial:
        valid = (
            details is not None
            and result.error is None
            and useful_count > 0
            and isinstance(details, ReadJobResult)
            and details.partial
            and bool(details.limitations)
        )
    elif result.status is JobStatus.failed:
        valid = result.error is not None and (
            details is None or (useful_count == 0 and not details.partial)
        )

    if valid:
        return result
    return JobHandlerResult.failed(
        category=JobFailureCategory.invariant_violation,
        retryable=False,
    )


@dataclass
class _ExecutionState:
    job_id: str
    lease_token: str
    job_type: str
    attempt_count: int
    lease_lost: bool = False
    cancelled: bool = False
    completed: asyncio.Event = None  # type: ignore[assignment]
    started_at: datetime | None = None
    job_created_at: datetime | None = None
    efficacy: EnrichmentEfficacySnapshot | None = None
    policy_label: str | None = None
    lease_loss_operation: str | None = None
    lease_loss_reported: bool = False
    transition_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    terminal_committed: bool = False

    def __post_init__(self) -> None:
        if self.completed is None:
            self.completed = asyncio.Event()


class Worker:
    def __init__(
        self,
        *,
        session_factory=None,
        handler_registry=None,
        settings: Settings | None = None,
        metrics=None,
        metrics_server_factory=None,
    ) -> None:
        self.settings = settings or get_settings()
        pod_name = os.environ.get("HOSTNAME", "worker")
        self.owner = f"{pod_name}-{id(self)}"
        self._session_factory = session_factory or AsyncSessionLocal
        self._uses_global_registry = handler_registry is None
        self._handler_registry = (
            handler_registry if handler_registry is not None else get_handler_registry()
        )
        self._metrics = metrics or metrics_registry
        self._metrics_server_factory = metrics_server_factory or start_metrics_server
        self._metrics_server: asyncio.AbstractServer | None = None
        self._shutdown_event = asyncio.Event()
        self._ready_event = asyncio.Event()
        self._executions: dict[str, _ExecutionState] = {}
        self._renewal_tasks: dict[str, asyncio.Task] = {}
        self._handler_tasks: dict[str, asyncio.Task] = {}

    def stop(self) -> None:
        self._shutdown_event.set()

    async def start(self) -> None:
        # Start the private readiness/metrics listener before dependency
        # validation so configuration and provider failures are promptly
        # observable as unavailable. Readiness stays false until handler
        # construction, contract validation, dependency validation, and
        # durable reconciliation succeed.
        self._metrics_server = await self._metrics_server_factory(
            host=self.settings.jobs_metrics_host,
            port=self.settings.jobs_metrics_port,
            render_prometheus=self._metrics.to_prometheus,
            is_ready=self._ready_event.is_set,
        )
        if self._metrics_server is None:
            raise RuntimeError("worker private metrics listener is unavailable")
        try:
            logger.info(
                "worker_starting",
                extra={
                    "ctx_owner": self.owner,
                    "ctx_poll_interval": self.settings.jobs_poll_interval_seconds,
                    "ctx_batch_size": self.settings.jobs_batch_size,
                    "ctx_concurrency": self.settings.jobs_worker_concurrency,
                    "ctx_lease_duration": self.settings.jobs_lease_duration_seconds,
                    "ctx_lease_renewal_interval": self.settings.jobs_lease_renewal_interval_seconds,
                    "ctx_drain_timeout": self.settings.jobs_shutdown_drain_seconds,
                    "ctx_registered_types": self._handler_registry.registered_types,
                },
            )
            if self.settings.jobs_worker_enabled:
                await self._poll_loop()
            else:
                logger.info("worker_disabled_by_configuration")
                await self._disabled_loop()
        finally:
            await self._drain()
            await stop_metrics_server(self._metrics_server)
            self._metrics_server = None

    async def _prepare_handler_registry(self) -> None:
        """Validate required contracts, constructing handlers only when active.

        An enabled worker constructs missing global handlers and validates
        contracts against the live registry. A disabled worker validates
        required contracts without constructing handlers or providers: the
        global production catalog is consulted when no explicit registry was
        supplied, and the explicit registry when one was. Synchronous
        construction runs off the event loop so a slow or failing production
        dependency cannot block readiness reporting. An explicitly supplied
        registry is never mutated: global handlers are constructed only when
        the worker uses the global registry.
        """
        if self.settings.jobs_worker_enabled:
            if self._uses_global_registry:
                await asyncio.to_thread(register_handlers, self._handler_registry)
            _validate_required_contracts(
                get_payload_model=self._handler_registry.get_payload_model,
                configured=self.settings.jobs_required_contracts,
            )
        elif self._uses_global_registry:
            _validate_required_contracts(
                get_payload_model=get_production_payload_model,
                configured=self.settings.jobs_required_contracts,
            )
        else:
            _validate_required_contracts(
                get_payload_model=self._handler_registry.get_payload_model,
                configured=self.settings.jobs_required_contracts,
            )

    async def _validate_dependencies(self) -> None:
        validation = await asyncio.to_thread(
            self._handler_registry.validate_dependencies
        )
        if inspect.isawaitable(validation):
            await validation

    async def _poll_loop(self) -> None:
        while not self._shutdown_event.is_set():
            try:
                await self._prepare_handler_registry()
                await self._validate_dependencies()
            except Exception:
                self._ready_event.clear()
                logger.warning(
                    "worker_dependency_validation_failed",
                    extra={
                        "ctx_failure_category": JobFailureCategory.invariant_violation.value
                    },
                )
                await self._refresh_backlog_metrics()
                if await self._wait_for_shutdown():
                    break
                continue
            try:
                await self._reconcile()
                self._metrics.record_worker_successful_poll()
                self._ready_event.set()
                await self._claim_batch()
                while not self._shutdown_event.is_set():
                    claimed = await self._claim_additional_if_capacity()
                    if not claimed:
                        break
            except asyncio.CancelledError:
                raise
            except Exception:
                self._ready_event.clear()
                logger.warning(
                    "worker_poll_failed",
                    extra={"ctx_failure_category": JobFailureCategory.database_transient.value},
                )
            if await self._wait_for_shutdown():
                break

    async def _disabled_loop(self) -> None:
        while not self._shutdown_event.is_set():
            try:
                await self._prepare_handler_registry()
                await self._check_database_connectivity()
                await self._refresh_backlog_metrics(propagate_errors=True)
                await self._refresh_durable_efficacy_metrics(propagate_errors=True)
                self._metrics.record_worker_successful_poll()
                self._ready_event.set()
            except asyncio.CancelledError:
                raise
            except Exception:
                self._ready_event.clear()
                logger.warning(
                    "worker_database_health_check_failed",
                    extra={
                        "ctx_failure_category": JobFailureCategory.database_transient.value
                    },
                )
            if await self._wait_for_shutdown():
                break

    async def _check_database_connectivity(self) -> None:
        async with self._session_factory() as session:
            await session.execute(text("SELECT 1"))

    async def _wait_for_shutdown(self) -> bool:
        try:
            await asyncio.wait_for(
                self._shutdown_event.wait(),
                timeout=self.settings.jobs_poll_interval_seconds,
            )
            return True
        except TimeoutError:
            return False

    async def _claim_additional_if_capacity(self) -> bool:
        """Fill remaining concurrency if eligible work exists. Returns True if a job was claimed."""
        active = len(self._executions)
        if active >= self.settings.jobs_worker_concurrency:
            return False
        remaining = self.settings.jobs_worker_concurrency - active
        capped = min(remaining, self.settings.jobs_batch_size)
        if capped <= 0:
            return False
        return bool(await self._claim(owner=self.owner, batch_size=capped))

    async def _reconcile(self) -> None:
        async with self._session_factory() as session:
            repo = JobRepository(session, self.settings)
            result = await repo.reconcile_expired_processing(
                batch_limit=self.settings.jobs_batch_size,
            )
            reconciliation_now = datetime.now(UTC)
            for job_id, raw_policy in result.exhausted_enrichment_jobs:
                created_at = result.exhausted_enrichment_job_created_at.get(job_id)
                completion_duration = (
                    max((reconciliation_now - created_at).total_seconds(), 0.0)
                    if created_at is not None
                    else 0.0
                )
                await repo.record_terminal_enrichment_observation(
                    job_id=job_id,
                    policy_label=enrichment_policy_label(raw_policy),
                    lifecycle_outcome="failed",
                    acquisition_avoided=False,
                    local_covered_count=0,
                    final_covered_count=0,
                    coverage_gain=0,
                    accepted_aspect_count=0,
                    search_count=0,
                    duration_seconds=completion_duration,
                )
            await session.commit()
        await self._refresh_durable_efficacy_metrics(propagate_errors=True)
        for job_type, count in result.exhausted_by_type.items():
            self._metrics.record_job_stale_recovery(
                job_type=job_type, outcome="attempts_exhausted", count=count
            )
            for _ in range(count):
                self._metrics.record_job_outcome(
                    job_type=job_type,
                    status=JobStatus.failed.value,
                    duration_seconds=0.0,
                )
            logger.info(
                "job_stale_recovered",
                extra={
                    "ctx_job_type": job_type,
                    "ctx_recovery_outcome": "attempts_exhausted",
                    "ctx_recovery_count": count,
                },
            )
        for job_type, count in result.recovered_by_type.items():
            self._metrics.record_job_stale_recovery(
                job_type=job_type, outcome="lease_expired", count=count
            )
            logger.info(
                "job_stale_recovered",
                extra={"ctx_job_type": job_type, "ctx_recovery_outcome": "lease_expired"},
            )
        await self._refresh_backlog_metrics()

    async def _refresh_backlog_metrics(self, *, propagate_errors: bool = False) -> None:
        try:
            async with self._session_factory() as session:
                repo = JobRepository(session, self.settings)
                counts = await repo.get_backlog_counts()
                status_counts = await repo.get_status_counts()
                age = await repo.oldest_eligible_age_seconds()
                await session.commit()
        except Exception:
            logger.warning(
                "worker_backlog_poll_failed",
                extra={"ctx_failure_category": "database_transient"},
            )
            if propagate_errors:
                raise
            return
        # Counts is the authoritative snapshot, including absent series.
        self._metrics.reset_job_backlog()
        self._metrics.reset_job_status_counts()
        for (job_type, status), count in counts.items():
            self._metrics.record_job_backlog(
                job_type=job_type, status=status, count=count,
            )
        for (job_type, status), count in status_counts.items():
            self._metrics.record_job_status_count(
                job_type=job_type, status=status, count=count,
            )
        self._metrics.record_oldest_eligible_age(age_seconds=age)

    async def _claim_batch(self) -> None:
        if self._shutdown_event.is_set():
            return
        active = len(self._executions)
        if active >= self.settings.jobs_worker_concurrency:
            return
        remaining = self.settings.jobs_worker_concurrency - active
        batch = min(remaining, self.settings.jobs_batch_size)
        if batch <= 0:
            return
        await self._claim(owner=self.owner, batch_size=batch)

    async def _claim(self, *, owner: str, batch_size: int) -> int:
        async with self._session_factory() as session:
            repo = JobRepository(session, self.settings)
            claimed = await repo.claim_jobs(
                owner=owner,
                batch_size=batch_size,
                lease_duration_seconds=self.settings.jobs_lease_duration_seconds,
            )

            if self._shutdown_event.is_set():
                await session.rollback()
                return 0

            if claimed:
                await session.commit()

            if self._shutdown_event.is_set():
                for job in claimed:
                    await repo.release_unstarted_job(
                        job_id=job.id,
                        owner=owner,
                        lease_token=job.lease_token,
                    )
                await session.commit()
                return 0

            # Register before leaving this context. Session exit awaits, so
            # registration after it would reopen a shutdown race.
            for job_row in claimed:
                self._register_execution(job_row)

        return len(claimed)

    def _register_execution(self, job_row: ClaimedJob) -> None:
        job_id = str(job_row.id)
        state = _ExecutionState(
            job_id=job_id,
            lease_token=job_row.lease_token,
            job_type=job_row.job_type.value,
            attempt_count=job_row.attempt_count,
            job_created_at=job_row.created_at,
        )
        self._executions[job_id] = state
        self._metrics.record_job_claim(job_type=job_row.job_type.value)
        if job_row.recovered:
            self._metrics.record_job_stale_recovery(
                job_type=job_row.job_type.value,
                outcome="lease_expired",
            )
            logger.info(
                "job_stale_recovered",
                extra={
                    "ctx_job_type": job_row.job_type.value,
                    "ctx_recovery_outcome": "lease_expired",
                    "ctx_recovery_count": 1,
                },
            )
        logger.info(
            "job_claimed",
            extra={
                "ctx_job_id": job_id,
                "ctx_job_type": job_row.job_type.value,
                "ctx_attempt": job_row.attempt_count,
                "ctx_worker_identity": self.owner,
                "ctx_recovered": job_row.recovered,
            },
        )
        task = asyncio.create_task(
            self._execute_handler(state=state, job_row=job_row),
            name=f"job:{job_id}",
        )
        self._handler_tasks[job_id] = task
        task.add_done_callback(self._make_done_callback(job_id))

    def _make_done_callback(self, job_id: str):
        def _done(task: asyncio.Task) -> None:
            self._handler_tasks.pop(job_id, None)
            self._executions.pop(job_id, None)
            renewal = self._renewal_tasks.pop(job_id, None)
            if renewal is not None and not renewal.done():
                renewal.cancel()
            if not task.cancelled() and task.exception() is not None:
                logger.error(
                    "worker_handler_task_failed",
                    extra={"ctx_job_id": job_id},
                )

        return _done

    async def _execute_handler(
        self,
        *,
        state: _ExecutionState,
        job_row: ClaimedJob,
    ) -> None:
        job_id = state.job_id
        job_type = state.job_type
        payload_version = job_row.payload_version
        payload = job_row.payload
        attempt_count = job_row.attempt_count
        max_attempts = job_row.max_attempts
        start = datetime.now(UTC)
        state.started_at = start
        raw_payload = payload if isinstance(payload, dict) else {}
        state.policy_label = enrichment_policy_label(
            raw_payload.get("policy_version")
        )

        renewal_task = asyncio.create_task(
            self._renew_lease_loop(state=state),
            name=f"renew:{job_id}",
        )
        self._renewal_tasks[job_id] = renewal_task

        result: JobHandlerResult | None = None
        try:
            result = await self._dispatch(
                state=state,
                job_type=job_type,
                payload_version=payload_version,
                payload=payload,
                attempt_count=attempt_count,
                max_attempts=max_attempts,
            )
            result = _validate_result_contract(result)
            state.efficacy = result.efficacy
        except asyncio.CancelledError:
            if not state.lease_lost:
                state.cancelled = True
                state.completed.set()
                duration = (datetime.now(UTC) - start).total_seconds()
                self._metrics.record_job_outcome(
                    job_type=job_type,
                    status="cancelled",
                    duration_seconds=duration,
                )
                logger.info(
                    "worker_handler_cancelled",
                    extra={
                        "ctx_job_id": job_id,
                        "ctx_job_type": job_type,
                        "ctx_attempt": attempt_count,
                        "ctx_worker_identity": self.owner,
                        "ctx_outcome": "cancelled",
                    },
                )
            raise
        except RetryableJobError as exc:
            result = JobHandlerResult.failed(category=exc.category, retryable=True)
        except PermanentJobError as exc:
            result = JobHandlerResult.failed(category=exc.category, retryable=False)
        except Exception:
            logger.warning(
                "worker_handler_exception",
                extra={
                    "ctx_job_id": job_id,
                    "ctx_job_type": job_type,
                    "ctx_attempt": attempt_count,
                    "ctx_worker_identity": self.owner,
                    "ctx_failure_category": JobFailureCategory.unexpected_error.value,
                },
            )
            result = JobHandlerResult.failed(
                category=JobFailureCategory.unexpected_error,
                retryable=True,
            )
        finally:
            if result is not None and not state.lease_lost and not state.cancelled:
                duration = (datetime.now(UTC) - start).total_seconds()
                await self._finalize_job(
                    state=state,
                    result=result,
                    attempt_count=attempt_count,
                    max_attempts=max_attempts,
                    duration=duration,
                )
            elif state.lease_lost:
                self._record_lease_loss(state, operation="execution")
            state.completed.set()

    async def _dispatch(
        self,
        *,
        state: _ExecutionState,
        job_type: str,
        payload_version: int,
        payload: dict[str, Any],
        attempt_count: int,
        max_attempts: int,
    ) -> JobHandlerResult:
        handler: JobHandler | None = self._handler_registry.get_handler(job_type)
        if handler is None:
            return JobHandlerResult.failed(
                category=JobFailureCategory.unknown_job_type,
                retryable=False,
            )

        model_cls = self._handler_registry.get_payload_model(
            job_type,
            payload_version,
        )
        if model_cls is None:
            return JobHandlerResult.failed(
                category=JobFailureCategory.unsupported_payload_version,
                retryable=False,
            )
        try:
            parsed_payload = model_cls.model_validate(payload)
        except ValidationError:
            return JobHandlerResult.failed(
                category=JobFailureCategory.invalid_payload,
                retryable=False,
            )
        if (
            job_type == JobType.enrich_confirmed_plant.value
            and isinstance(parsed_payload, EnrichConfirmedPlantPayload)
            and str(parsed_payload.run_id) != state.job_id
        ):
            return JobHandlerResult.failed(
                category=JobFailureCategory.invariant_violation,
                retryable=False,
            )
        return await handler.handle(
            payload=parsed_payload,
            attempt_count=attempt_count,
            max_attempts=max_attempts,
        )

    async def _finalize_job(
        self,
        *,
        state: _ExecutionState,
        result: JobHandlerResult,
        attempt_count: int,
        max_attempts: int,
        duration: float,
    ) -> None:
        """Serialize the terminal transition against lease renewal.

        The transition lock is shared with ``_renew_lease_loop`` so a renewal
        that loses the race against finalization sees the completed or
        terminal-committed execution and never records a false lease loss.
        """
        async with state.transition_lock:
            if state.lease_lost or state.cancelled:
                return
            await self._finalize_job_locked(
                state=state,
                result=result,
                attempt_count=attempt_count,
                max_attempts=max_attempts,
                duration=duration,
            )
            state.completed.set()

    async def _finalize_job_locked(
        self,
        *,
        state: _ExecutionState,
        result: JobHandlerResult,
        attempt_count: int,
        max_attempts: int,
        duration: float,
    ) -> None:
        job_id = state.job_id
        lease_token = state.lease_token
        job_type = state.job_type
        is_last_attempt = attempt_count >= max_attempts

        async with self._session_factory() as session:
            repo = JobRepository(session, self.settings)

            if result.status == JobStatus.complete:
                success = await repo.complete_job(
                    job_id=job_id, owner=self.owner,
                    lease_token=lease_token, result=result.result,
                )
                if not success:
                    await session.rollback()
                    self._record_lease_loss(state, operation="complete")
                    return
                if state.job_type == JobType.enrich_confirmed_plant.value:
                    await self._record_observation_in_session(
                        repo, state=state, outcome="complete", duration=self._completion_duration_seconds(state)
                    )
                await session.commit()
                state.terminal_committed = True
                self._metrics.record_job_outcome(
                    job_type=job_type, status=JobStatus.complete.value, duration_seconds=duration
                )
                await self._refresh_durable_efficacy_metrics(propagate_errors=False)
                logger.info(
                    "job_completed",
                    extra={
                        "ctx_job_id": job_id,
                        "ctx_job_type": job_type,
                        "ctx_attempt": attempt_count,
                        "ctx_duration": duration,
                        "ctx_worker_identity": self.owner,
                        "ctx_outcome": JobStatus.complete.value,
                    },
                )
                return

            if result.status == JobStatus.partial:
                success = await repo.partial_job(
                    job_id=job_id, owner=self.owner,
                    lease_token=lease_token, result=result.result,
                )
                if not success:
                    await session.rollback()
                    self._record_lease_loss(state, operation="partial")
                    return
                if state.job_type == JobType.enrich_confirmed_plant.value:
                    await self._record_observation_in_session(
                        repo, state=state, outcome="partial", duration=self._completion_duration_seconds(state)
                    )
                await session.commit()
                state.terminal_committed = True
                self._metrics.record_job_outcome(
                    job_type=job_type, status=JobStatus.partial.value, duration_seconds=duration
                )
                await self._refresh_durable_efficacy_metrics(propagate_errors=False)
                logger.info(
                    "job_partial",
                    extra={
                        "ctx_job_id": job_id,
                        "ctx_job_type": job_type,
                        "ctx_attempt": attempt_count,
                        "ctx_duration": duration,
                        "ctx_worker_identity": self.owner,
                        "ctx_outcome": JobStatus.partial.value,
                        "ctx_limitations": [
                            limitation.value for limitation in result.result.limitations
                        ]
                        if result.result
                        else [],
                    },
                )
                return

            failure_category = (
                result.error.category
                if result.error
                else JobFailureCategory.unexpected_error
            )
            should_retry = (
                result.error.retryable if result.error else _is_retryable(failure_category)
            )

            if not is_last_attempt and should_retry:
                retry_delay_seconds = repo.compute_backoff_seconds(
                    attempt_count=attempt_count,
                )
                success = await repo.retry_job(
                    job_id=job_id, owner=self.owner,
                    lease_token=lease_token,
                    error=JobError(category=failure_category, retryable=True),
                    delay_seconds=retry_delay_seconds,
                )
                if not success:
                    await session.rollback()
                    self._record_lease_loss(state, operation="retry")
                    return
                await session.commit()
                self._metrics.record_job_outcome(
                    job_type=job_type, status="retry_scheduled",
                    duration_seconds=duration,
                )
                self._metrics.record_job_retry(
                    job_type=job_type, category=failure_category.value,
                )
                logger.info(
                    "job_retry_scheduled",
                    extra={
                        "ctx_job_id": job_id,
                        "ctx_job_type": job_type,
                        "ctx_attempt": attempt_count,
                        "ctx_failure_category": failure_category.value,
                        "ctx_duration": duration,
                        "ctx_worker_identity": self.owner,
                        "ctx_outcome": "retry_scheduled",
                        "ctx_retry_delay_seconds": retry_delay_seconds,
                    },
                )
                return

            success = await repo.fail_job(
                job_id=job_id, owner=self.owner,
                lease_token=lease_token,
                error=JobError(category=failure_category, retryable=False),
                result=result.result,
            )
            if not success:
                await session.rollback()
                self._record_lease_loss(state, operation="fail")
                return
            if state.job_type == JobType.enrich_confirmed_plant.value:
                await self._record_observation_in_session(
                    repo, state=state, outcome="failed", duration=self._completion_duration_seconds(state)
                )
            await session.commit()
            state.terminal_committed = True
            self._metrics.record_job_outcome(
                job_type=job_type, status=JobStatus.failed.value, duration_seconds=duration
            )
            await self._refresh_durable_efficacy_metrics(propagate_errors=False)
            logger.info(
                "job_failed",
                extra={
                    "ctx_job_id": job_id,
                    "ctx_job_type": job_type,
                    "ctx_attempt": attempt_count,
                    "ctx_duration": duration,
                    "ctx_failure_category": failure_category.value,
                    "ctx_worker_identity": self.owner,
                    "ctx_outcome": JobStatus.failed.value,
                },
            )

    def _completion_duration_seconds(self, state: _ExecutionState) -> float:
        """Enqueue-to-terminal duration for durable enrichment efficacy."""
        if state.job_created_at is None:
            return 0.0
        return max(
            (datetime.now(UTC) - state.job_created_at).total_seconds(), 0.0
        )

    async def _record_observation_in_session(
        self,
        repo: JobRepository,
        *,
        state: _ExecutionState,
        outcome: str,
        duration: float,
    ) -> None:
        """Insert the immutable terminal enrichment observation in the same
        transaction as the terminal job transition. Never called for retries
        or non-enrichment jobs. ``duration`` is the completion duration from
        job creation to the terminal commit."""
        snapshot = state.efficacy
        if snapshot is None:
            policy_label = state.policy_label or "unsupported"
            acquisition_avoided = False
            local_covered_count = 0
            final_covered_count = 0
            coverage_gain = 0
            accepted_aspect_count = 0
            search_count = 0
        else:
            policy_label = enrichment_policy_label(snapshot.policy_version)
            acquisition_avoided = snapshot.acquisition_avoided
            local_covered_count = snapshot.local_covered_count
            final_covered_count = snapshot.final_covered_count
            coverage_gain = snapshot.coverage_gain
            accepted_aspect_count = snapshot.accepted_aspect_count
            search_count = snapshot.search_count
        await repo.record_terminal_enrichment_observation(
            job_id=UUID(state.job_id),
            policy_label=policy_label,
            lifecycle_outcome=outcome,
            acquisition_avoided=acquisition_avoided,
            local_covered_count=local_covered_count,
            final_covered_count=final_covered_count,
            coverage_gain=coverage_gain,
            accepted_aspect_count=accepted_aspect_count,
            search_count=search_count,
            duration_seconds=max(duration, 0.0),
        )

    async def _refresh_durable_efficacy_metrics(
        self, *, propagate_errors: bool = False
    ) -> None:
        """Replace the in-memory efficacy snapshot from durable observations.

        Replacement, not increment: repeated refreshes and worker restarts
        render the same totals. Multiple replicas expose identical
        database-derived totals, so monitoring aggregates with max.

        During readiness establishment (enabled reconciliation and disabled
        pause health) failures must propagate so readiness stays ``503``.
        After an already-committed terminal job, a rendering failure must not
        undo the committed terminal transition, so it is only logged.
        """
        try:
            async with self._session_factory() as session:
                repo = JobRepository(session, self.settings)
                totals = await repo.get_enrichment_efficacy_totals()
                await session.commit()
        except Exception:
            logger.warning(
                "worker_efficacy_metrics_refresh_failed",
                extra={
                    "ctx_failure_category": JobFailureCategory.database_transient.value
                },
            )
            if propagate_errors:
                raise
            return
        self._metrics.replace_enrichment_efficacy(totals)

    def _record_lease_loss(self, state: _ExecutionState, *, operation: str) -> None:
        """Consolidated idempotent lease-loss reporting: one canonical warning
        and one bounded generic job outcome, preserving the first detected
        operation. Lease loss is never a terminal enrichment efficacy outcome."""
        state.lease_lost = True
        if state.lease_loss_operation is None:
            state.lease_loss_operation = operation
        if state.lease_loss_reported:
            return
        state.lease_loss_reported = True
        duration = 0.0
        if state.started_at is not None:
            duration = max(
                (datetime.now(UTC) - state.started_at).total_seconds(), 0.0
            )
        self._metrics.record_job_outcome(
            job_type=state.job_type,
            status="lease_lost",
            duration_seconds=duration,
        )
        logger.warning(
            "worker_lease_lost",
            extra={
                "ctx_job_id": state.job_id,
                "ctx_job_type": state.job_type,
                "ctx_attempt": state.attempt_count,
                "ctx_worker_identity": self.owner,
                "ctx_operation": state.lease_loss_operation,
            },
        )

    async def _renew_lease_loop(self, *, state: _ExecutionState) -> None:
        # Active handlers retain ownership while the worker drains. Renewal stops
        # only when execution finishes or the drain timeout cancels the handler.
        while not state.completed.is_set():
            try:
                await asyncio.wait_for(
                    state.completed.wait(),
                    timeout=self.settings.jobs_lease_renewal_interval_seconds,
                )
                return
            except TimeoutError:
                pass
            if state.completed.is_set():
                return
            # Serialize against finalization with the shared transition lock.
            # If finalization already committed a terminal transition, renewal
            # must return silently: a successfully finalized handler can never
            # report a false lease loss. The renewal session is opened only
            # after the lock is acquired so no stale read can race the commit.
            async with state.transition_lock:
                if state.completed.is_set() or state.terminal_committed:
                    return
                try:
                    async with self._session_factory() as session:
                        repo = JobRepository(session, self.settings)
                        renewed = await repo.renew_lease(
                            job_id=state.job_id,
                            owner=self.owner,
                            lease_token=state.lease_token,
                            lease_duration_seconds=self.settings.jobs_lease_duration_seconds,
                        )
                        if renewed:
                            await session.commit()
                            logger.info(
                                "job_lease_renewed",
                                extra={
                                    "ctx_job_id": state.job_id,
                                    "ctx_job_type": state.job_type,
                                    "ctx_attempt": state.attempt_count,
                                    "ctx_worker_identity": self.owner,
                                },
                            )
                        else:
                            self._record_lease_loss(state, operation="renewal")
                            handler_task = self._handler_tasks.get(state.job_id)
                            if handler_task is not None and not handler_task.done():
                                handler_task.cancel()
                            await session.rollback()
                            return
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.warning(
                        "worker_lease_renewal_error",
                        extra={
                            "ctx_job_id": state.job_id,
                            "ctx_job_type": state.job_type,
                            "ctx_attempt": state.attempt_count,
                            "ctx_worker_identity": self.owner,
                            "ctx_failure_category": JobFailureCategory.database_transient.value,
                        },
                    )

    async def _drain(self) -> None:
        self._ready_event.clear()
        active = len(self._executions)
        logger.info(
            "worker_draining",
            extra={
                "ctx_active_count": active,
                "ctx_drain_timeout": self.settings.jobs_shutdown_drain_seconds,
            },
        )
        if not self._executions:
            logger.info(
                "worker_stopped",
                extra={"ctx_outcome": "clean"},
            )
            return

        tasks = list(self._handler_tasks.values())
        _, pending = await asyncio.wait(
            tasks,
            timeout=self.settings.jobs_shutdown_drain_seconds,
        )
        timed_out = bool(pending)

        if timed_out:
            for state in list(self._executions.values()):
                if not state.completed.is_set():
                    state.cancelled = True
                    state.completed.set()
            for task in pending:
                task.cancel()

        renewal_tasks = list(self._renewal_tasks.values())
        for renewal in renewal_tasks:
            if not renewal.done():
                renewal.cancel()

        cleanup_tasks = {*pending, *renewal_tasks}
        lingering: set[asyncio.Task] = set()
        if cleanup_tasks:
            _, lingering = await asyncio.wait(
                cleanup_tasks,
                timeout=CANCELLATION_CLEANUP_TIMEOUT_SECONDS,
            )
        if lingering:
            logger.warning(
                "worker_cancellation_cleanup_timeout",
                extra={
                    "ctx_remaining": len(lingering),
                    "ctx_cleanup_timeout": CANCELLATION_CLEANUP_TIMEOUT_SECONDS,
                },
            )
        # Let completion callbacks finish before the worker task returns.
        await asyncio.sleep(0)

        if timed_out:
            logger.warning(
                "worker_drain_timeout",
                extra={"ctx_remaining": len(pending)},
            )
            logger.info(
                "worker_stopped",
                extra={"ctx_outcome": "timeout"},
            )
        else:
            logger.info(
                "worker_stopped",
                extra={"ctx_outcome": "clean"},
            )

    def active_executions(self) -> list[str]:
        return list(self._executions.keys())


def _handle_signal(worker: Worker) -> None:
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, worker.stop)
    logger.info("worker_signal_handlers_registered")


async def async_main() -> None:
    configure_logging(get_settings().log_level)
    logger.info("worker_entrypoint_starting")
    worker = Worker()
    _handle_signal(worker)
    await worker.start()


def run_worker() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    run_worker()
