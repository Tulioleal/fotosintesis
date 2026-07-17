from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy import func, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.tables import application_jobs
from app.core.settings import Settings, get_settings
from app.db.repository import RepositoryBase
from app.jobs.schemas import (
    ClaimedJob,
    JobError,
    JobFailureCategory,
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


@dataclass(frozen=True)
class EnqueueResult:
    job_id: UUID
    created: bool


class RepositoryInvariantError(RuntimeError):
    pass


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
        now = datetime.now(timezone.utc)

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
            "max_attempts": max_attempts or self.settings.jobs_max_attempts_default,
            "available_at": available_at or now,
            "created_at": now,
            "updated_at": now,
        }

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
                    AND lease_expires_at <= CURRENT_TIMESTAMP
                    AND attempt_count < max_attempts
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
                    aj.available_at,
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
            },
        )
        rows = result.fetchall()
        return [ClaimedJob.model_validate(row._mapping) for row in rows]

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
        result: ReadJobResult | None = None,
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
            )
        )
        return transition.rowcount > 0

    async def partial_job(
        self,
        *,
        job_id: UUID,
        owner: str,
        lease_token: str,
        result: ReadJobResult | None = None,
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
                status=JobStatus.partial.value,
                result=result.model_dump(mode="json") if result is not None else None,
                completed_at=func.now(),
                updated_at=func.now(),
                lease_owner=None,
                lease_token=None,
                lease_expires_at=None,
            )
        )
        return transition.rowcount > 0

    async def retry_job(
        self,
        *,
        job_id: UUID,
        owner: str,
        lease_token: str,
        error: JobError,
        available_at: datetime,
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
                status=JobStatus.pending.value,
                last_error=error.model_dump(mode="json"),
                available_at=available_at,
                updated_at=func.now(),
                lease_owner=None,
                lease_token=None,
                lease_expires_at=None,
            )
        )
        return transition.rowcount > 0

    async def fail_job(
        self,
        *,
        job_id: UUID,
        owner: str,
        lease_token: str,
        error: JobError,
        result: ReadJobResult | None = None,
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
            )
        )
        return transition.rowcount > 0

    async def reconcile_expired_processing(
        self, *, batch_limit: int | None = None
    ) -> ReconciliationResult:
        now = datetime.now(timezone.utc)
        limit = batch_limit or 100
        rows = (
            await self.session.execute(
                select(
                    application_jobs.c.id,
                    application_jobs.c.job_type,
                    application_jobs.c.attempt_count,
                    application_jobs.c.max_attempts,
                )
                .where(
                    application_jobs.c.status == JobStatus.processing.value,
                    application_jobs.c.lease_expires_at.is_not(None),
                    application_jobs.c.lease_expires_at <= now,
                )
                .order_by(application_jobs.c.lease_expires_at.asc())
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        ).mappings().all()

        recovered: dict[str, int] = {}
        exhausted: dict[str, int] = {}
        for row in rows:
            job_type = row["job_type"]
            attempt_count = row["attempt_count"]
            max_attempts = row["max_attempts"]
            if attempt_count >= max_attempts:
                exhausted[job_type] = exhausted.get(job_type, 0) + 1
                await self.session.execute(
                    update(application_jobs)
                    .where(application_jobs.c.id == row["id"])
                    .values(
                        status=JobStatus.failed.value,
                        last_error=JobError(
                            category=JobFailureCategory.attempts_exhausted,
                            retryable=False,
                        ).model_dump(mode="json"),
                        completed_at=now,
                        updated_at=now,
                        lease_owner=None,
                        lease_token=None,
                        lease_expires_at=None,
                    )
                )
            else:
                recovered[job_type] = recovered.get(job_type, 0) + 1
                # Per-row exponential backoff based on the actual attempt count.
                base = self.settings.jobs_backoff_base_seconds
                cap = self.settings.jobs_backoff_cap_seconds
                exponent = max(attempt_count - 1, 0)
                delay = min(base * (2 ** exponent), cap)
                await self.session.execute(
                    update(application_jobs)
                    .where(application_jobs.c.id == row["id"])
                    .values(
                        status=JobStatus.pending.value,
                        last_error=JobError(
                            category=JobFailureCategory.lease_expired,
                            retryable=True,
                        ).model_dump(mode="json"),
                        available_at=now + timedelta(seconds=delay),
                        completed_at=None,
                        updated_at=now,
                        lease_owner=None,
                        lease_token=None,
                        lease_expires_at=None,
                    )
                )

        return ReconciliationResult(
            recovered_by_type=recovered,
            exhausted_by_type=exhausted,
        )

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

    def compute_backoff(self, *, attempt_count: int) -> datetime:
        if attempt_count <= 1:
            delay = self.settings.jobs_backoff_base_seconds
        else:
            delay = self.settings.jobs_backoff_base_seconds * (2 ** (attempt_count - 1))
        delay = min(delay, self.settings.jobs_backoff_cap_seconds)
        return datetime.now(timezone.utc) + timedelta(seconds=delay)

    def _row_to_status_response(self, row: dict) -> JobStatusResponse:
        last_error_raw = row.get("last_error")
        last_error = None
        if last_error_raw:
            last_error = ReadJobError.model_validate(last_error_raw)
        result_raw = row.get("result")
        result = None
        if result_raw:
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
