from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import and_, func, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.tables import (
    application_jobs,
    candidate_enrichment_jobs,
    enrichment_telemetry_observations,
    identification_candidates,
    identification_images,
)
from app.core.settings import Settings, get_settings
from app.db.repository import RepositoryBase
from app.enrichment.policy import enrichment_policy_label
from app.jobs.schemas import (
    CandidateEnrichmentStatus,
    ClaimedJob,
    EnrichmentJobResult,
    JobError,
    JobFailureCategory,
    JobResult,
    JobStatus,
    JobStatusResponse,
    JobType,
    ReadJobError,
    ReadJobResult,
)


@dataclass(frozen=True)
class ReconciliationResult:
    recovered_by_type: dict[str, int]
    exhausted_by_type: dict[str, int]
    exhausted_enrichment_jobs: list[tuple[UUID, object]] = field(default_factory=list)
    exhausted_enrichment_job_created_at: dict[UUID, datetime] = field(default_factory=dict)
    exhausted_enrichment_terminals: list["EnrichmentTerminalReconciliation"] = field(
        default_factory=list
    )


@dataclass(frozen=True)
class EnrichmentTerminalReconciliation:
    """Typed terminal facts for a crashed exhausted enrichment job.

    The worker inserts the matching immutable observation from these durable
    facts in the same transaction as the terminal job transition.
    """

    job_id: UUID
    status: JobStatus
    policy_label: str
    lifecycle_outcome: str
    acquisition_avoided: bool
    local_covered_count: int
    final_covered_count: int
    coverage_gain: int
    accepted_aspect_count: int
    search_count: int
    duration_seconds: float
    result: EnrichmentJobResult | None
    last_error: JobError


ENRICHMENT_TELEMETRY_POLICY_LABELS = frozenset({"1", "unsupported"})
ENRICHMENT_TELEMETRY_LIFECYCLE_OUTCOMES = frozenset({"complete", "partial", "failed"})
ENRICHMENT_TELEMETRY_COUNT_BOUNDS = {
    "local_covered_count": (0, 100),
    "final_covered_count": (0, 100),
    "accepted_aspect_count": (0, 100),
    "search_count": (0, 100),
}
ENRICHMENT_TELEMETRY_GAIN_BOUNDS = (-100, 100)


def validate_enrichment_observation_values(
    *,
    local_covered_count: object,
    final_covered_count: object,
    coverage_gain: object,
    accepted_aspect_count: object,
    search_count: object,
    duration_seconds: object,
) -> None:
    """Validate observation values against the database constraints.

    A malformed handler snapshot must never be silently rewritten to fit the
    database: counts must be integers (never booleans) within their bounds,
    and the duration must be finite and non-negative. Raises ``ValueError``
    before any SQL is issued.
    """
    counts = {
        "local_covered_count": local_covered_count,
        "final_covered_count": final_covered_count,
        "accepted_aspect_count": accepted_aspect_count,
        "search_count": search_count,
    }
    for name, value in counts.items():
        if type(value) is not int:
            raise ValueError(
                f"{name} must be an integer, not {type(value).__name__}"
            )
        lower, upper = ENRICHMENT_TELEMETRY_COUNT_BOUNDS[name]
        if not lower <= value <= upper:
            raise ValueError(f"{name} must be within {lower}..{upper}")
    if type(coverage_gain) is not int:
        raise ValueError(
            f"coverage_gain must be an integer, not {type(coverage_gain).__name__}"
        )
    lower, upper = ENRICHMENT_TELEMETRY_GAIN_BOUNDS
    if not lower <= coverage_gain <= upper:
        raise ValueError(f"coverage_gain must be within {lower}..{upper}")
    if not math.isfinite(float(duration_seconds)):
        raise ValueError("duration_seconds must be finite")
    if duration_seconds < 0:
        raise ValueError("duration_seconds must be non-negative")


@dataclass(frozen=True)
class EnqueueResult:
    job_id: UUID
    created: bool


@dataclass(frozen=True)
class CandidateEnrichmentAssociationResult:
    job_id: UUID
    job_created: bool
    association_created: bool


class RepositoryInvariantError(RuntimeError):
    pass


def recovery_backoff_seconds(
    *,
    attempt_count: int,
    base: float,
    cap: float,
) -> float:
    exponent = max(attempt_count - 1, 0)
    return min(base * (2**exponent), cap)


def canonical_idempotency_key(
    *,
    job_type: str,
    conversation_id: UUID | None,
    claims_hash: str,
    payload_version: int,
    ingestion_policy_version: int,
) -> str:
    raw = json.dumps(
        {
            "jt": job_type,
            "cid": str(conversation_id or ""),
            "ch": claims_hash,
            "pv": payload_version,
            "ipv": ingestion_policy_version,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(raw.encode()).hexdigest()


def compute_claims_hash(claims: list[dict]) -> str:
    normalized = sorted(
        json.dumps(c, sort_keys=True, ensure_ascii=False) for c in claims
    )
    return hashlib.sha256("".join(normalized).encode()).hexdigest()


class JobRepository(RepositoryBase):
    def __init__(
        self, session: AsyncSession, settings: Settings | None = None
    ) -> None:
        super().__init__(session)
        self.settings = settings or get_settings()

    async def enqueue(
        self,
        *,
        job_type: str,
        payload_version: int,
        payload: dict,
        idempotency_key: str,
        user_id: UUID | None = None,
        conversation_id: UUID | None = None,
        max_attempts: int | None = None,
        available_at: datetime | None = None,
    ) -> UUID:
        result = await self.enqueue_result(
            job_type=job_type,
            payload_version=payload_version,
            payload=payload,
            idempotency_key=idempotency_key,
            user_id=user_id,
            conversation_id=conversation_id,
            max_attempts=max_attempts,
            available_at=available_at,
        )
        return result.job_id

    async def enqueue_result(
        self,
        *,
        job_type: str,
        payload_version: int,
        payload: dict,
        idempotency_key: str,
        user_id: UUID | None = None,
        conversation_id: UUID | None = None,
        max_attempts: int | None = None,
        available_at: datetime | None = None,
    ) -> EnqueueResult:
        validated_job_type = JobType(job_type)
        resolved_max_attempts = (
            self.settings.jobs_max_attempts_default
            if max_attempts is None
            else max_attempts
        )
        if resolved_max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")

        job_id = uuid4()
        insert_values = {
            "id": job_id,
            "user_id": user_id,
            "conversation_id": conversation_id,
            "job_type": validated_job_type.value,
            "payload_version": payload_version,
            "payload": payload,
            "status": JobStatus.pending.value,
            "idempotency_key": idempotency_key,
            "max_attempts": resolved_max_attempts,
        }
        if available_at is not None:
            insert_values["available_at"] = available_at

        stmt = (
            pg_insert(application_jobs)
            .values(**insert_values)
            .on_conflict_do_nothing(
                index_elements=["job_type", "idempotency_key"],
            )
            .returning(application_jobs.c.id)
        )
        result = await self.session.execute(stmt)
        row = result.first()
        if row is not None:
            return EnqueueResult(job_id=row._mapping["id"], created=True)

        existing = (
            await self.session.execute(
                select(application_jobs.c.id).where(
                    application_jobs.c.job_type == validated_job_type.value,
                    application_jobs.c.idempotency_key == idempotency_key,
                )
            )
        ).first()
        if existing is not None:
            return EnqueueResult(job_id=existing._mapping["id"], created=False)

        raise RepositoryInvariantError(
            "idempotent enqueue conflict completed without a visible winner"
        )

    async def enqueue_active_enrichment(
        self,
        *,
        payload_version: int,
        payload: dict,
        idempotency_key: str,
        active_deduplication_key: str,
        max_attempts: int = 3,
    ) -> EnqueueResult:
        if not active_deduplication_key.strip():
            raise ValueError("active_deduplication_key must not be blank")
        existing_run = (
            await self.session.execute(
                select(application_jobs.c.id).where(
                    application_jobs.c.job_type
                    == JobType.enrich_confirmed_plant.value,
                    application_jobs.c.idempotency_key == idempotency_key,
                )
            )
        ).first()
        if existing_run is not None:
            return EnqueueResult(existing_run._mapping["id"], created=False)

        try:
            job_id = UUID(str(payload["run_id"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("active enrichment payload requires a valid run_id") from exc
        active_predicate = and_(
            application_jobs.c.active_deduplication_key.is_not(None),
            application_jobs.c.status.in_(
                [JobStatus.pending.value, JobStatus.processing.value]
            ),
        )
        statement = (
            pg_insert(application_jobs)
            .values(
                id=job_id,
                job_type=JobType.enrich_confirmed_plant.value,
                payload_version=payload_version,
                payload=payload,
                status=JobStatus.pending.value,
                idempotency_key=idempotency_key,
                active_deduplication_key=active_deduplication_key,
                max_attempts=max_attempts,
            )
            .on_conflict_do_nothing(
                index_elements=[application_jobs.c.active_deduplication_key],
                index_where=active_predicate,
            )
            .returning(application_jobs.c.id)
        )
        inserted = (await self.session.execute(statement)).first()
        if inserted is not None:
            return EnqueueResult(inserted._mapping["id"], created=True)

        active = (
            await self.session.execute(
                select(application_jobs.c.id).where(
                    application_jobs.c.active_deduplication_key
                    == active_deduplication_key,
                    application_jobs.c.status.in_(
                        [JobStatus.pending.value, JobStatus.processing.value]
                    ),
                )
            )
        ).first()
        if active is not None:
            return EnqueueResult(active._mapping["id"], created=False)
        raise RepositoryInvariantError(
            "active enrichment conflict completed without a visible winner"
        )

    async def associate_candidate_enrichment(
        self,
        *,
        candidate_id: UUID,
        user_id: UUID,
        policy_version: int,
        payload_version: int,
        payload: dict,
        idempotency_key: str,
        active_deduplication_key: str,
        max_attempts: int = 3,
    ) -> CandidateEnrichmentAssociationResult:
        owned_candidate = await self.session.scalar(
            select(identification_candidates.c.id)
            .join(
                identification_images,
                identification_images.c.id
                == identification_candidates.c.identification_id,
            )
            .where(
                identification_candidates.c.id == candidate_id,
                identification_images.c.user_id == user_id,
            )
        )
        if owned_candidate is None:
            raise ValueError("candidate is not owned by the requesting user")

        existing = (
            await self.session.execute(
                select(candidate_enrichment_jobs.c.job_id).where(
                    candidate_enrichment_jobs.c.candidate_id == candidate_id,
                    candidate_enrichment_jobs.c.policy_version == policy_version,
                )
            )
        ).first()
        if existing is not None:
            return CandidateEnrichmentAssociationResult(
                job_id=existing._mapping["job_id"],
                job_created=False,
                association_created=False,
            )

        enqueue = await self.enqueue_active_enrichment(
            payload_version=payload_version,
            payload=payload,
            idempotency_key=idempotency_key,
            active_deduplication_key=active_deduplication_key,
            max_attempts=max_attempts,
        )
        association_id = uuid4()
        inserted = (
            await self.session.execute(
                pg_insert(candidate_enrichment_jobs)
                .values(
                    id=association_id,
                    user_id=user_id,
                    candidate_id=candidate_id,
                    job_id=enqueue.job_id,
                    policy_version=policy_version,
                )
                .on_conflict_do_nothing(
                    index_elements=[
                        candidate_enrichment_jobs.c.candidate_id,
                        candidate_enrichment_jobs.c.policy_version,
                    ]
                )
                .returning(candidate_enrichment_jobs.c.job_id)
            )
        ).first()
        if inserted is not None:
            return CandidateEnrichmentAssociationResult(
                job_id=inserted._mapping["job_id"],
                job_created=enqueue.created,
                association_created=True,
            )
        winner = (
            await self.session.execute(
                select(candidate_enrichment_jobs.c.job_id).where(
                    candidate_enrichment_jobs.c.candidate_id == candidate_id,
                    candidate_enrichment_jobs.c.policy_version == policy_version,
                )
            )
        ).first()
        if winner is None:
            raise RepositoryInvariantError(
                "candidate enrichment conflict completed without a visible winner"
            )
        return CandidateEnrichmentAssociationResult(
            job_id=winner._mapping["job_id"],
            job_created=False,
            association_created=False,
        )

    async def claim_jobs(
        self, *, owner: str, batch_size: int, lease_duration_seconds: float
    ) -> list[ClaimedJob]:
        stmt = text("""
            WITH claimed AS (
                SELECT id, status AS previous_status
                FROM application_jobs
                WHERE (
                    status = 'pending'
                    AND available_at <= CURRENT_TIMESTAMP
                    AND attempt_count < max_attempts
                ) OR (
                    status = 'processing'
                    AND lease_expires_at IS NOT NULL
                    AND attempt_count < max_attempts
                    AND lease_expires_at
                        + (
                            LEAST(
                                :backoff_base * POWER(
                                    2,
                                    GREATEST(attempt_count - 1, 0)
                                ),
                                :backoff_cap
                            ) * INTERVAL '1 second'
                        ) <= CURRENT_TIMESTAMP
                )
                ORDER BY available_at ASC
                LIMIT :batch_size
                FOR UPDATE SKIP LOCKED
            ),
            updated AS (
                UPDATE application_jobs AS aj
                SET
                    status = 'processing',
                    attempt_count = aj.attempt_count + 1,
                    lease_owner = :owner,
                    lease_token = :lease_token,
                    lease_expires_at = CURRENT_TIMESTAMP + (:lease_seconds * INTERVAL '1 second'),
                    updated_at = CURRENT_TIMESTAMP
                FROM claimed
                WHERE aj.id = claimed.id
                RETURNING
                    aj.id, aj.job_type, aj.payload_version, aj.payload,
                    aj.attempt_count, aj.max_attempts, aj.conversation_id,
                    aj.lease_owner, aj.lease_token, aj.lease_expires_at,
                    aj.available_at, aj.created_at,
                    (claimed.previous_status = 'processing') AS recovered
            )
            SELECT * FROM updated ORDER BY available_at ASC
        """)
        result = await self.session.execute(
            stmt,
            {
                "batch_size": batch_size,
                "owner": owner,
                "lease_token": str(uuid4()),
                "lease_seconds": lease_duration_seconds,
                "backoff_base": self.settings.jobs_backoff_base_seconds,
                "backoff_cap": self.settings.jobs_backoff_cap_seconds,
            },
        )
        rows = result.fetchall()
        return [ClaimedJob.model_validate(row._mapping) for row in rows]

    async def release_unstarted_job(
        self,
        *,
        job_id: UUID,
        owner: str,
        lease_token: str,
    ) -> bool:
        transition = await self.session.execute(
            update(application_jobs)
            .where(
                application_jobs.c.id == job_id,
                application_jobs.c.status == JobStatus.processing.value,
                application_jobs.c.lease_owner == owner,
                application_jobs.c.lease_token == lease_token,
            )
            .values(
                status=JobStatus.pending.value,
                attempt_count=func.greatest(
                    application_jobs.c.attempt_count - 1,
                    0,
                ),
                available_at=func.now(),
                lease_owner=None,
                lease_token=None,
                lease_expires_at=None,
                updated_at=func.now(),
            )
        )
        return transition.rowcount > 0

    async def renew_lease(
        self, *, job_id: UUID, owner: str, lease_token: str, lease_duration_seconds: float
    ) -> bool:
        result = await self.session.execute(
            update(application_jobs)
            .where(
                application_jobs.c.id == job_id,
                application_jobs.c.lease_owner == owner,
                application_jobs.c.lease_token == lease_token,
                application_jobs.c.status == JobStatus.processing.value,
                application_jobs.c.lease_expires_at > func.now(),
            )
            .values(
                lease_expires_at=func.now() + timedelta(seconds=lease_duration_seconds),
                updated_at=func.now(),
            )
        )
        return result.rowcount > 0

    async def complete_job(
        self,
        *,
        job_id: UUID,
        owner: str,
        lease_token: str,
        result: JobResult | None = None,
    ) -> bool:
        transition = await self.session.execute(
            update(application_jobs)
            .where(
                application_jobs.c.id == job_id,
                application_jobs.c.lease_owner == owner,
                application_jobs.c.lease_token == lease_token,
                application_jobs.c.status == JobStatus.processing.value,
                application_jobs.c.lease_expires_at > func.now(),
            )
            .values(
                status=JobStatus.complete.value,
                result=result.model_dump(mode="json") if result is not None else None,
                completed_at=func.now(),
                updated_at=func.now(),
                lease_owner=None,
                lease_token=None,
                lease_expires_at=None,
                active_deduplication_key=None,
                last_error=None,
            )
        )
        return transition.rowcount > 0

    async def partial_job(
        self,
        *,
        job_id: UUID,
        owner: str,
        lease_token: str,
        result: JobResult | None = None,
        error: JobError | None = None,
    ) -> bool:
        values: dict[str, object] = {
            "status": JobStatus.partial.value,
            "result": result.model_dump(mode="json") if result is not None else None,
            "completed_at": func.now(),
            "updated_at": func.now(),
            "lease_owner": None,
            "lease_token": None,
            "lease_expires_at": None,
            "active_deduplication_key": None,
        }
        if error is not None:
            values["last_error"] = error.model_dump(mode="json")
        else:
            values["last_error"] = None
        transition = await self.session.execute(
            update(application_jobs)
            .where(
                application_jobs.c.id == job_id,
                application_jobs.c.lease_owner == owner,
                application_jobs.c.lease_token == lease_token,
                application_jobs.c.status == JobStatus.processing.value,
                application_jobs.c.lease_expires_at > func.now(),
            )
            .values(**values)
        )
        return transition.rowcount > 0

    async def retry_job(
        self,
        *,
        job_id: UUID,
        owner: str,
        lease_token: str,
        error: JobError,
        delay_seconds: float,
    ) -> bool:
        if not math.isfinite(delay_seconds) or delay_seconds < 0:
            raise ValueError("delay_seconds must be finite and non-negative")
        if self.session.bind and self.session.bind.dialect.name == "postgresql":
            available_at = func.now() + text(
                "(:retry_delay_seconds * INTERVAL '1 second')"
            )
        else:
            # SQLite only backs repository unit tests; production scheduling is PostgreSQL.
            available_at = func.datetime(func.now(), f"+{delay_seconds} seconds")
        transition = await self.session.execute(
            update(application_jobs)
            .where(
                application_jobs.c.id == job_id,
                application_jobs.c.lease_owner == owner,
                application_jobs.c.lease_token == lease_token,
                application_jobs.c.status == JobStatus.processing.value,
                application_jobs.c.lease_expires_at > func.now(),
            )
            .values(
                status=JobStatus.pending.value,
                last_error=error.model_dump(mode="json"),
                available_at=available_at,
                updated_at=func.now(),
                lease_owner=None,
                lease_token=None,
                lease_expires_at=None,
            ),
            {"retry_delay_seconds": delay_seconds},
        )
        return transition.rowcount > 0

    async def fail_job(
        self,
        *,
        job_id: UUID,
        owner: str,
        lease_token: str,
        error: JobError,
        result: JobResult | None = None,
    ) -> bool:
        transition = await self.session.execute(
            update(application_jobs)
            .where(
                application_jobs.c.id == job_id,
                application_jobs.c.lease_owner == owner,
                application_jobs.c.lease_token == lease_token,
                application_jobs.c.status == JobStatus.processing.value,
                application_jobs.c.lease_expires_at > func.now(),
            )
            .values(
                status=JobStatus.failed.value,
                last_error=error.model_dump(mode="json"),
                result=result.model_dump(mode="json") if result is not None else None,
                completed_at=func.now(),
                updated_at=func.now(),
                lease_owner=None,
                lease_token=None,
                lease_expires_at=None,
                active_deduplication_key=None,
            )
        )
        return transition.rowcount > 0

    async def reconcile_expired_processing(
        self, *, batch_limit: int | None = None
    ) -> ReconciliationResult:
        limit = batch_limit or 100
        rows = (
            await self.session.execute(
                select(
                    application_jobs.c.id,
                    application_jobs.c.job_type,
                    application_jobs.c.attempt_count,
                    application_jobs.c.max_attempts,
                    application_jobs.c.lease_expires_at,
                    application_jobs.c.payload,
                    application_jobs.c.created_at,
                )
                .where(
                    application_jobs.c.status == JobStatus.processing.value,
                    application_jobs.c.lease_expires_at.is_not(None),
                    application_jobs.c.lease_expires_at <= func.now(),
                )
                .order_by(application_jobs.c.lease_expires_at.asc())
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        ).mappings().all()

        recovered: dict[str, int] = {}
        exhausted: dict[str, int] = {}
        exhausted_enrichment_jobs: list[tuple[UUID, object]] = []
        exhausted_enrichment_job_created_at: dict[UUID, datetime] = {}
        exhausted_enrichment_terminals: list[EnrichmentTerminalReconciliation] = []
        now = datetime.now(UTC)
        for row in rows:
            job_type = row["job_type"]
            attempt_count = row["attempt_count"]
            max_attempts = row["max_attempts"]
            if attempt_count >= max_attempts:
                exhausted[job_type] = exhausted.get(job_type, 0) + 1
                if job_type == JobType.enrich_confirmed_plant.value:
                    raw_payload = row["payload"]
                    raw_policy = (
                        raw_payload.get("policy_version")
                        if isinstance(raw_payload, dict)
                        else None
                    )
                    exhausted_enrichment_jobs.append((row["id"], raw_policy))
                    exhausted_enrichment_job_created_at[row["id"]] = row["created_at"]
                    terminal = await self._reconcile_exhausted_enrichment(
                        job_id=row["id"],
                        raw_policy=raw_policy,
                        created_at=row["created_at"],
                        now=now,
                    )
                    exhausted_enrichment_terminals.append(terminal)
                else:
                    await self.session.execute(
                        update(application_jobs)
                        .where(application_jobs.c.id == row["id"])
                        .values(
                            status=JobStatus.failed.value,
                            last_error=JobError(
                                category=JobFailureCategory.attempts_exhausted,
                                retryable=False,
                            ).model_dump(mode="json"),
                            completed_at=func.now(),
                            updated_at=func.now(),
                            lease_owner=None,
                            lease_token=None,
                            lease_expires_at=None,
                            active_deduplication_key=None,
                        )
                    )
            else:
                recovered[job_type] = recovered.get(job_type, 0) + 1
                delay = recovery_backoff_seconds(
                    attempt_count=attempt_count,
                    base=self.settings.jobs_backoff_base_seconds,
                    cap=self.settings.jobs_backoff_cap_seconds,
                )
                await self.session.execute(
                    update(application_jobs)
                    .where(application_jobs.c.id == row["id"])
                    .values(
                        status=JobStatus.pending.value,
                        last_error=JobError(
                            category=JobFailureCategory.lease_expired,
                            retryable=True,
                        ).model_dump(mode="json"),
                        available_at=row["lease_expires_at"] + timedelta(seconds=delay),
                        completed_at=None,
                        updated_at=func.now(),
                        lease_owner=None,
                        lease_token=None,
                        lease_expires_at=None,
                    )
                )

        return ReconciliationResult(
            recovered_by_type=recovered,
            exhausted_by_type=exhausted,
            exhausted_enrichment_jobs=exhausted_enrichment_jobs,
            exhausted_enrichment_job_created_at=exhausted_enrichment_job_created_at,
            exhausted_enrichment_terminals=exhausted_enrichment_terminals,
        )

    async def _reconcile_exhausted_enrichment(
        self,
        *,
        job_id: UUID,
        raw_policy: object,
        created_at: datetime,
        now: datetime,
    ) -> EnrichmentTerminalReconciliation:
        """Reconcile a crashed exhausted enrichment job from durable progress.

        Useful checkpoint coverage finalizes as ``partial`` with bounded
        result metadata; otherwise the job finalizes as ``failed``. The
        terminal transition clears the lease and active deduplication key and
        stores the closed ``attempts_exhausted`` error. The returned typed
        record lets the worker insert the matching immutable observation in
        the same transaction.
        """
        from app.enrichment.progress import (
            EnrichmentProgressRepository,
            build_efficacy_snapshot,
            build_failure_terminal_result,
            select_operational_limitation,
        )

        progress = EnrichmentProgressRepository(self.session)
        snapshot = await progress.get_for_terminalization(
            job_id=job_id,
            for_update=True,
        )
        operational = select_operational_limitation(
            snapshot,
            is_last_attempt=True,
        )
        status, result, closed_error = build_failure_terminal_result(
            snapshot,
            failure_category=JobFailureCategory.attempts_exhausted,
            operational_limitation=operational,
        )
        values: dict[str, object] = {
            "status": status.value,
            "last_error": closed_error.model_dump(mode="json"),
            "completed_at": func.now(),
            "updated_at": func.now(),
            "lease_owner": None,
            "lease_token": None,
            "lease_expires_at": None,
            "active_deduplication_key": None,
        }
        if result is not None:
            values["result"] = result.model_dump(mode="json")
        await self.session.execute(
            update(application_jobs)
            .where(application_jobs.c.id == job_id)
            .values(**values)
        )
        duration_seconds = max((now - created_at).total_seconds(), 0.0)
        if snapshot is None:
            return EnrichmentTerminalReconciliation(
                job_id=job_id,
                status=status,
                policy_label=enrichment_policy_label(raw_policy),
                lifecycle_outcome=status.value,
                acquisition_avoided=False,
                local_covered_count=0,
                final_covered_count=0,
                coverage_gain=0,
                accepted_aspect_count=0,
                search_count=0,
                duration_seconds=duration_seconds,
                result=result,
                last_error=closed_error,
            )
        efficacy = build_efficacy_snapshot(snapshot)
        return EnrichmentTerminalReconciliation(
            job_id=job_id,
            status=status,
            policy_label=enrichment_policy_label(snapshot.policy_version),
            lifecycle_outcome=status.value,
            acquisition_avoided=efficacy.acquisition_avoided,
            local_covered_count=efficacy.local_covered_count,
            final_covered_count=efficacy.final_covered_count,
            coverage_gain=efficacy.coverage_gain,
            accepted_aspect_count=efficacy.accepted_aspect_count,
            search_count=efficacy.search_count,
            duration_seconds=duration_seconds,
            result=result,
            last_error=closed_error,
        )

    async def record_terminal_enrichment_observation(
        self,
        *,
        job_id: UUID,
        policy_label: str,
        lifecycle_outcome: str,
        acquisition_avoided: bool,
        local_covered_count: int,
        final_covered_count: int,
        coverage_gain: int,
        accepted_aspect_count: int,
        search_count: int,
        duration_seconds: float,
    ) -> None:
        """Insert one immutable enrichment observation.

        Runs in the same transaction as the terminal job transition. A
        replayed identical insert is harmless; a differing existing row is an
        invariant violation because immutable observations can never change.
        Retries and non-enrichment jobs must never call this.
        """
        if policy_label not in ENRICHMENT_TELEMETRY_POLICY_LABELS:
            raise ValueError(
                f"unsupported enrichment telemetry policy label: {policy_label!r}"
            )
        if lifecycle_outcome not in ENRICHMENT_TELEMETRY_LIFECYCLE_OUTCOMES:
            raise ValueError(
                f"unsupported enrichment telemetry outcome: {lifecycle_outcome!r}"
            )
        validate_enrichment_observation_values(
            local_covered_count=local_covered_count,
            final_covered_count=final_covered_count,
            coverage_gain=coverage_gain,
            accepted_aspect_count=accepted_aspect_count,
            search_count=search_count,
            duration_seconds=duration_seconds,
        )
        values = {
            "job_id": job_id,
            "policy_label": policy_label,
            "lifecycle_outcome": lifecycle_outcome,
            "acquisition_avoided": bool(acquisition_avoided),
            "local_covered_count": local_covered_count,
            "final_covered_count": final_covered_count,
            "coverage_gain": coverage_gain,
            "accepted_aspect_count": accepted_aspect_count,
            "search_count": search_count,
            "duration_seconds": float(duration_seconds),
        }
        await self.session.execute(
            pg_insert(enrichment_telemetry_observations)
            .values(**values)
            .on_conflict_do_nothing(
                index_elements=[enrichment_telemetry_observations.c.job_id]
            )
        )
        existing = (
            await self.session.execute(
                select(enrichment_telemetry_observations).where(
                    enrichment_telemetry_observations.c.job_id == job_id
                )
            )
        ).mappings().first()
        if existing is None:
            return
        comparable = {
            "job_id": existing["job_id"],
            "policy_label": existing["policy_label"],
            "lifecycle_outcome": existing["lifecycle_outcome"],
            "acquisition_avoided": bool(existing["acquisition_avoided"]),
            "local_covered_count": existing["local_covered_count"],
            "final_covered_count": existing["final_covered_count"],
            "coverage_gain": existing["coverage_gain"],
            "accepted_aspect_count": existing["accepted_aspect_count"],
            "search_count": existing["search_count"],
            "duration_seconds": float(existing["duration_seconds"]),
        }
        if comparable != values:
            raise RepositoryInvariantError(
                f"immutable enrichment observation already exists for job {job_id}"
            )

    async def get_enrichment_efficacy_totals(self):
        """Aggregate durable efficacy telemetry in PostgreSQL.

        Returns grouped counts (by policy label, lifecycle outcome, and
        acquisition avoidance) plus per-histogram value counts, sums, and
        fixed-boundary bucket counts, instead of loading every historical
        observation into Python. The result shape mirrors
        ``EnrichmentEfficacyTotals`` from ``app.observability.metrics``.
        """
        from app.observability.metrics import (
            ENRICHMENT_COUNT_BUCKETS,
            JOB_DURATION_BUCKETS,
            EnrichmentEfficacyTotals,
            Histogram,
        )

        count_rows = (
            await self.session.execute(
                select(
                    enrichment_telemetry_observations.c.policy_label,
                    enrichment_telemetry_observations.c.lifecycle_outcome,
                    enrichment_telemetry_observations.c.acquisition_avoided,
                    func.count().label("count"),
                ).group_by(
                    enrichment_telemetry_observations.c.policy_label,
                    enrichment_telemetry_observations.c.lifecycle_outcome,
                    enrichment_telemetry_observations.c.acquisition_avoided,
                )
            )
        ).all()
        counts: dict[tuple[str, str, bool], int] = {
            (
                row.policy_label,
                row.lifecycle_outcome,
                bool(row.acquisition_avoided),
            ): row.count
            for row in count_rows
        }

        histograms: dict[tuple[str, str, str], Histogram] = {}
        column_buckets = {
            "local_covered_count": ("local_covered_count", ENRICHMENT_COUNT_BUCKETS),
            "final_covered_count": ("final_covered_count", ENRICHMENT_COUNT_BUCKETS),
            "coverage_gain": ("coverage_gain", ENRICHMENT_COUNT_BUCKETS),
            "accepted_aspect_count": (
                "accepted_aspect_count",
                ENRICHMENT_COUNT_BUCKETS,
            ),
            "search_count": ("search_count", ENRICHMENT_COUNT_BUCKETS),
            "completion_duration_seconds": (
                "duration_seconds",
                JOB_DURATION_BUCKETS,
            ),
        }
        for histogram_name, (column_name, buckets) in column_buckets.items():
            column = getattr(
                enrichment_telemetry_observations.c, column_name
            )
            aggregate_rows = (
                await self.session.execute(
                    select(
                        enrichment_telemetry_observations.c.policy_label,
                        enrichment_telemetry_observations.c.lifecycle_outcome,
                        func.count().label("count"),
                        func.coalesce(func.sum(column), 0.0).label("sum"),
                    ).group_by(
                        enrichment_telemetry_observations.c.policy_label,
                        enrichment_telemetry_observations.c.lifecycle_outcome,
                    )
                )
            ).all()
            grouped: dict[tuple[str, str], Histogram] = {}
            for row in aggregate_rows:
                histogram = Histogram(buckets=buckets)
                histogram.total_count = row.count
                histogram.total_sum = float(row.sum)
                grouped[(row.policy_label, row.lifecycle_outcome)] = histogram
                histograms[
                    (histogram_name, row.policy_label, row.lifecycle_outcome)
                ] = histogram
            for boundary_index, boundary in enumerate(buckets):
                bucket_rows = (
                    await self.session.execute(
                        select(
                            enrichment_telemetry_observations.c.policy_label,
                            enrichment_telemetry_observations.c.lifecycle_outcome,
                            func.count().label("count"),
                        )
                        .where(column <= boundary)
                        .group_by(
                            enrichment_telemetry_observations.c.policy_label,
                            enrichment_telemetry_observations.c.lifecycle_outcome,
                        )
                    )
                ).all()
                for row in bucket_rows:
                    grouped[(row.policy_label, row.lifecycle_outcome)].counts[
                        boundary_index
                    ] = row.count
        return EnrichmentEfficacyTotals(counts=counts, histograms=histograms)

    async def get_job_status(self, *, job_id: UUID, user_id: UUID) -> JobStatusResponse | None:
        row = (
            await self.session.execute(
                select(application_jobs).where(
                    application_jobs.c.id == job_id,
                    application_jobs.c.user_id == user_id,
                )
            )
        ).first()
        if row is None:
            return None
        return self._row_to_status_response(row._mapping)

    async def get_candidate_enrichment_status(
        self,
        *,
        candidate_id: UUID,
        user_id: UUID,
        policy_version: int,
    ) -> CandidateEnrichmentStatus | None:
        row = (
            await self.session.execute(
                select(application_jobs)
                .join(
                    candidate_enrichment_jobs,
                    candidate_enrichment_jobs.c.job_id == application_jobs.c.id,
                )
                .join(
                    identification_candidates,
                    identification_candidates.c.id
                    == candidate_enrichment_jobs.c.candidate_id,
                )
                .join(
                    identification_images,
                    identification_images.c.id
                    == identification_candidates.c.identification_id,
                )
                .where(
                    candidate_enrichment_jobs.c.candidate_id == candidate_id,
                    candidate_enrichment_jobs.c.policy_version == policy_version,
                    candidate_enrichment_jobs.c.user_id == user_id,
                    identification_images.c.user_id == user_id,
                )
            )
        ).first()
        if row is None:
            return None
        return CandidateEnrichmentStatus(
            candidate_id=candidate_id,
            policy_version=policy_version,
            job=self._row_to_status_response(row._mapping),
        )

    async def get_backlog_counts(self) -> dict[tuple[str, str], int]:
        rows = (
            await self.session.execute(
                select(
                    application_jobs.c.status,
                    application_jobs.c.job_type,
                    func.count().label("count"),
                )
                .where(application_jobs.c.status.in_(["pending", "processing"]))
                .group_by(application_jobs.c.status, application_jobs.c.job_type)
            )
        ).all()
        counts: dict[tuple[str, str], int] = {}
        for row in rows:
            counts[(row._mapping["job_type"], row._mapping["status"])] = (
                row._mapping["count"]
            )
        return counts

    async def get_status_counts(self) -> dict[tuple[str, str], int]:
        rows = (
            await self.session.execute(
                select(
                    application_jobs.c.status,
                    application_jobs.c.job_type,
                    func.count().label("count"),
                ).group_by(application_jobs.c.status, application_jobs.c.job_type)
            )
        ).all()
        return {
            (row._mapping["job_type"], row._mapping["status"]): row._mapping[
                "count"
            ]
            for row in rows
        }

    async def oldest_eligible_age_seconds(self) -> float | None:
        row = (
            await self.session.execute(
                select(
                    func.extract("epoch", func.now() - application_jobs.c.available_at).label("age")
                )
                .where(
                    application_jobs.c.status == JobStatus.pending.value,
                    application_jobs.c.available_at <= func.now(),
                )
                .order_by(application_jobs.c.available_at.asc())
                .limit(1)
            )
        ).first()
        if row is None:
            return None
        return float(row._mapping["age"])

    def compute_backoff_seconds(self, *, attempt_count: int) -> float:
        return recovery_backoff_seconds(
            attempt_count=attempt_count,
            base=self.settings.jobs_backoff_base_seconds,
            cap=self.settings.jobs_backoff_cap_seconds,
        )

    def _row_to_status_response(self, row: dict) -> JobStatusResponse:
        last_error_raw = row.get("last_error")
        last_error = None
        if last_error_raw:
            last_error = ReadJobError.model_validate(last_error_raw)
        result_raw = row.get("result")
        result = None
        if result_raw:
            if row["job_type"] == JobType.enrich_confirmed_plant.value:
                result = EnrichmentJobResult.model_validate(result_raw)
            else:
                result = ReadJobResult(
                    succeeded=result_raw.get("succeeded", 0),
                    skipped=result_raw.get("skipped", 0),
                    failed=result_raw.get("failed", 0),
                    partial=result_raw.get("partial", False),
                    limitations=result_raw.get("limitations", []),
                )
        return JobStatusResponse(
            id=row["id"],
            job_type=row["job_type"],
            status=JobStatus(row["status"]),
            attempt_count=row["attempt_count"],
            max_attempts=row["max_attempts"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            completed_at=row.get("completed_at"),
            result=result,
            last_error=last_error,
        )
