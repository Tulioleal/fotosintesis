"""Durable enrichment progress checkpoints.

Each enrichment job owns one ``enrichment_job_progress`` row that records
immutable policy/aspect identity and only-growing coverage sets. The worker
finalizes partial or failed outcomes from this checkpoint instead of a
handler's zero snapshot, so useful accepted evidence is never reported as a
total failure. Unknown or malformed policies fail closed.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.tables import enrichment_job_progress
from app.enrichment.policy import EnrichmentPolicy, get_enrichment_policy
from app.jobs.handler import EnrichmentEfficacySnapshot
from app.jobs.schemas import (
    EnrichmentJobResult,
    EnrichmentLimitation,
    JobError,
    JobFailureCategory,
    JobStatus,
)

MAX_ASPECT_COUNT = 32
MAX_COUNT_BOUND = 100
ANSWERABILITY_STATUSES = frozenset(
    {"full", "partial", "insufficient", "contradictory"}
)


def _normalize_aspects(
    aspects: object,
    *,
    policy: EnrichmentPolicy,
    allow_unsorted: bool = True,
) -> tuple[str, ...]:
    """Deduplicate and validate a bounded aspect collection against a policy."""
    if aspects is None:
        return ()
    if not isinstance(aspects, (list, tuple, set, frozenset)):
        raise ValueError("enrichment progress aspects must be a collection")
    allowed = {aspect.value for aspect in policy.required_aspects}
    normalized: list[str] = []
    for raw in aspects:
        if not isinstance(raw, str) or not raw.strip():
            raise ValueError("enrichment progress aspects must be non-empty strings")
        value = raw.strip()
        if value not in allowed:
            raise ValueError(
                f"enrichment progress aspect {value!r} is not part of the selected policy"
            )
        if value not in normalized:
            normalized.append(value)
    if len(normalized) > MAX_ASPECT_COUNT:
        raise ValueError(f"enrichment progress aspects exceed {MAX_ASPECT_COUNT}")
    return tuple(normalized)


def _sorted_unique(aspects: object) -> tuple[str, ...]:
    if not aspects:
        return ()
    return tuple(sorted(dict.fromkeys(str(item) for item in aspects)))


def _merge_unique(*collections: object) -> tuple[str, ...]:
    merged: set[str] = set()
    for collection in collections:
        if collection:
            merged.update(str(item) for item in collection)
    return tuple(sorted(merged))


@dataclass(frozen=True)
class EnrichmentJobProgress:
    """Durable progress snapshot for one enrichment job."""

    job_id: UUID
    policy_version: int
    required_aspects: tuple[str, ...]
    local_covered_aspects: tuple[str, ...] = ()
    persisted_covered_aspects: tuple[str, ...] = ()
    indexed_covered_aspects: tuple[str, ...] = ()
    final_judged_covered_aspects: tuple[str, ...] | None = None
    final_judged_missing_aspects: tuple[str, ...] | None = None
    answerability_status: str | None = None
    acquisition_avoided: bool = False
    search_count: int = 0
    accepted_aspect_count: int = 0
    last_validation_run_id: UUID | None = None

    @property
    def has_useful_coverage(self) -> bool:
        return bool(self.coverage_aspects)

    @property
    def coverage_aspects(self) -> tuple[str, ...]:
        """Return accepted coverage that survived a durable workflow boundary.

        Final judging is diagnostic until its source support passes claim
        selection and persistence. Counting judge-only aspects here could turn
        an operational failure with no accepted evidence into a false partial.
        """
        covered = set(self.local_covered_aspects)
        covered.update(self.persisted_covered_aspects)
        return tuple(sorted(covered))

    @property
    def missing_aspects(self) -> tuple[str, ...]:
        covered = set(self.coverage_aspects)
        return tuple(
            aspect for aspect in self.required_aspects if aspect not in covered
        )


class EnrichmentProgressRepository:
    """Repository for the durable per-job progress checkpoint.

    Methods never commit: callers own the transaction boundary so each
    progress update is committed atomically with its paired evidence
    transition. This guarantees a progress failure rolls back the evidence
    changes and vice versa.
    """

    def __init__(
        self,
        session: AsyncSession,
        policy_resolver=get_enrichment_policy,
    ) -> None:
        self.session = session
        self._policy_resolver = policy_resolver

    def _policy(self, policy_version: int) -> EnrichmentPolicy:
        return self._policy_resolver(policy_version)

    async def initialize_or_load(
        self,
        *,
        job_id: UUID,
        policy_version: int,
        required_aspects: object,
    ) -> EnrichmentJobProgress:
        policy = self._policy(policy_version)
        required = _normalize_aspects(required_aspects, policy=policy)
        if not required:
            raise ValueError("enrichment progress requires at least one aspect")
        existing = await self._load(job_id)
        if existing is not None:
            if existing.policy_version != policy_version:
                raise ValueError(
                    "enrichment progress policy version is immutable after initialization"
                )
            if set(existing.required_aspects) != set(required):
                raise ValueError(
                    "enrichment progress required aspects are immutable after initialization"
                )
            return existing
        await self.session.execute(
            enrichment_job_progress.insert().values(
                job_id=job_id,
                policy_version=policy_version,
                required_aspects=list(required),
                local_covered_aspects=[],
                persisted_covered_aspects=[],
                indexed_covered_aspects=[],
            )
        )
        row = (
            await self.session.execute(
                select(enrichment_job_progress).where(
                    enrichment_job_progress.c.job_id == job_id
                )
            )
        ).first()
        if row is None:
            raise RuntimeError("enrichment progress row disappeared after initialization")
        return _row_to_progress(row._mapping)

    async def _load(
        self,
        job_id: UUID,
        *,
        for_update: bool = False,
    ) -> EnrichmentJobProgress | None:
        statement = select(enrichment_job_progress).where(
            enrichment_job_progress.c.job_id == job_id
        )
        if for_update:
            statement = statement.with_for_update()
        row = (
            await self.session.execute(statement)
        ).first()
        return _row_to_progress(row._mapping) if row is not None else None

    async def _require(
        self,
        job_id: UUID,
        *,
        for_update: bool = False,
    ) -> EnrichmentJobProgress:
        snapshot = await self._load(job_id, for_update=for_update)
        if snapshot is None:
            raise ValueError("enrichment progress checkpoint is not initialized")
        return snapshot

    async def record_local_coverage(
        self,
        *,
        job_id: UUID,
        local_covered_aspects: object,
    ) -> EnrichmentJobProgress:
        snapshot = await self._require(job_id, for_update=True)
        policy = self._policy(snapshot.policy_version)
        new_local = _normalize_aspects(local_covered_aspects, policy=policy)
        merged = _merge_unique(snapshot.local_covered_aspects, new_local)
        await self._update(
            job_id,
            local_covered_aspects=list(merged),
        )
        return replace(snapshot, local_covered_aspects=merged)

    async def record_acquisition_summary(
        self,
        *,
        job_id: UUID,
        acquisition_avoided: bool,
        search_count: int,
    ) -> EnrichmentJobProgress:
        snapshot = await self._require(job_id, for_update=True)
        if type(search_count) is not int or search_count < 0:
            raise ValueError("search_count must be a non-negative integer")
        bounded = min(search_count, MAX_COUNT_BOUND)
        merged = min(snapshot.search_count + bounded, MAX_COUNT_BOUND)
        await self._update(
            job_id,
            acquisition_avoided=bool(acquisition_avoided),
            search_count=merged,
        )
        return replace(
            snapshot,
            acquisition_avoided=bool(acquisition_avoided),
            search_count=merged,
        )

    async def record_persisted_aspects(
        self,
        *,
        job_id: UUID,
        persisted_aspects: object,
    ) -> EnrichmentJobProgress:
        snapshot = await self._require(job_id, for_update=True)
        policy = self._policy(snapshot.policy_version)
        new_persisted = _normalize_aspects(persisted_aspects, policy=policy)
        merged = _merge_unique(snapshot.persisted_covered_aspects, new_persisted)
        await self._update(
            job_id,
            persisted_covered_aspects=list(merged),
            accepted_aspect_count=min(len(merged), MAX_COUNT_BOUND),
        )
        return replace(
            snapshot,
            persisted_covered_aspects=merged,
            accepted_aspect_count=min(len(merged), MAX_COUNT_BOUND),
        )

    async def record_indexed_aspects(
        self,
        *,
        job_id: UUID,
        indexed_aspects: object,
    ) -> EnrichmentJobProgress:
        snapshot = await self._require(job_id, for_update=True)
        policy = self._policy(snapshot.policy_version)
        new_indexed = _normalize_aspects(indexed_aspects, policy=policy)
        permitted = set(snapshot.persisted_covered_aspects)
        permitted.update(snapshot.local_covered_aspects)
        for aspect in new_indexed:
            if aspect not in permitted:
                raise ValueError(
                    "indexed aspects must be a subset of persisted or local coverage"
                )
        merged = _merge_unique(snapshot.indexed_covered_aspects, new_indexed)
        await self._update(
            job_id,
            indexed_covered_aspects=list(merged),
        )
        return replace(snapshot, indexed_covered_aspects=merged)

    async def record_final_judging(
        self,
        *,
        job_id: UUID,
        final_covered_aspects: object,
        final_missing_aspects: object,
        answerability_status: str | None,
        last_validation_run_id: UUID | None = None,
    ) -> EnrichmentJobProgress:
        snapshot = await self._require(job_id, for_update=True)
        policy = self._policy(snapshot.policy_version)
        covered = _normalize_aspects(final_covered_aspects, policy=policy)
        missing = _normalize_aspects(final_missing_aspects, policy=policy)
        required = set(snapshot.required_aspects)
        if set(covered) & set(missing):
            raise ValueError("final judged aspects must be disjoint")
        if set(covered) | set(missing) != required:
            raise ValueError("final judged aspects must partition the policy aspects")
        if answerability_status is not None:
            if answerability_status not in ANSWERABILITY_STATUSES:
                raise ValueError(
                    f"unsupported enrichment answerability status: {answerability_status!r}"
                )
        await self._update(
            job_id,
            final_judged_covered_aspects=list(covered),
            final_judged_missing_aspects=list(missing),
            answerability_status=answerability_status,
            last_validation_run_id=last_validation_run_id,
        )
        return replace(
            snapshot,
            final_judged_covered_aspects=covered,
            final_judged_missing_aspects=missing,
            answerability_status=answerability_status,
            last_validation_run_id=last_validation_run_id,
        )

    async def get_for_terminalization(
        self,
        *,
        job_id: UUID,
        for_update: bool = False,
    ) -> EnrichmentJobProgress | None:
        return await self._load(job_id, for_update=for_update)

    async def _update(self, job_id: UUID, **values: object) -> None:
        await self.session.execute(
            update(enrichment_job_progress)
            .where(enrichment_job_progress.c.job_id == job_id)
            .values(updated_at=func.now(), **values)
        )


def _row_to_progress(row) -> EnrichmentJobProgress:
    return EnrichmentJobProgress(
        job_id=row["job_id"],
        policy_version=row["policy_version"],
        required_aspects=_sorted_unique(row["required_aspects"]),
        local_covered_aspects=_sorted_unique(row["local_covered_aspects"]),
        persisted_covered_aspects=_sorted_unique(row["persisted_covered_aspects"]),
        indexed_covered_aspects=_sorted_unique(row["indexed_covered_aspects"]),
        final_judged_covered_aspects=(
            _sorted_unique(row["final_judged_covered_aspects"])
            if row["final_judged_covered_aspects"] is not None
            else None
        ),
        final_judged_missing_aspects=(
            _sorted_unique(row["final_judged_missing_aspects"])
            if row["final_judged_missing_aspects"] is not None
            else None
        ),
        answerability_status=row["answerability_status"],
        acquisition_avoided=bool(row["acquisition_avoided"]),
        search_count=int(row["search_count"]),
        accepted_aspect_count=int(row["accepted_aspect_count"]),
        last_validation_run_id=row["last_validation_run_id"],
    )


def build_failure_terminal_result(
    snapshot: EnrichmentJobProgress | None,
    *,
    failure_category: JobFailureCategory,
    operational_limitation: EnrichmentLimitation | None = None,
) -> tuple[JobStatus, EnrichmentJobResult | None, JobError]:
    """Decide the terminal outcome for a failed enrichment attempt.

    Returns ``(status, result, error)``. When the durable checkpoint has
    useful accepted coverage the job finalizes as ``partial`` with bounded
    covered/missing aspects and the closed failure error. Otherwise it
    finalizes as ``failed`` without a result.
    """
    closed_error = JobError(category=failure_category, retryable=False)
    if snapshot is None or not snapshot.has_useful_coverage:
        return JobStatus.failed, None, closed_error

    covered = list(snapshot.coverage_aspects)
    missing = list(snapshot.missing_aspects)
    limitations: list[EnrichmentLimitation] = []
    if missing:
        limitations.append(EnrichmentLimitation.missing_required_aspects)
    if operational_limitation is not None:
        limitations.append(operational_limitation)
    result = EnrichmentJobResult(
        outcome="partial",
        policy_version=snapshot.policy_version,
        covered_aspects=covered,
        missing_aspects=missing,
        covered_count=len(covered),
        missing_count=len(missing),
        limitations=limitations,
        acquisition_avoided=snapshot.acquisition_avoided,
    )
    return JobStatus.partial, result, closed_error


def build_efficacy_snapshot(
    snapshot: EnrichmentJobProgress,
) -> EnrichmentEfficacySnapshot:
    """Build bounded terminal efficacy telemetry from durable progress."""
    final_covered_count = len(snapshot.coverage_aspects)
    local_covered_count = len(snapshot.local_covered_aspects)
    return EnrichmentEfficacySnapshot(
        policy_version=snapshot.policy_version,
        acquisition_avoided=snapshot.acquisition_avoided,
        local_covered_count=local_covered_count,
        final_covered_count=final_covered_count,
        coverage_gain=final_covered_count - local_covered_count,
        accepted_aspect_count=snapshot.accepted_aspect_count,
        search_count=snapshot.search_count,
    )


def select_operational_limitation(
    snapshot: EnrichmentJobProgress | None,
    *,
    is_last_attempt: bool,
) -> EnrichmentLimitation:
    """Select the operational limitation from the actual unfinished stage.

    Accepted evidence that persisted but was never fully indexed is an
    ``indexing_deferred`` limitation even when attempts are exhausted. An
    exhausted final attempt without deferred indexing is
    ``retry_exhausted``; an interrupted non-final attempt is
    ``workflow_incomplete``.
    """
    if snapshot is not None:
        persisted = set(snapshot.persisted_covered_aspects)
        indexed = set(snapshot.indexed_covered_aspects)
        if persisted and not persisted.issubset(indexed):
            return EnrichmentLimitation.indexing_deferred
    if is_last_attempt:
        return EnrichmentLimitation.retry_exhausted
    return EnrichmentLimitation.workflow_incomplete


__all__ = [
    "ANSWERABILITY_STATUSES",
    "EnrichmentJobProgress",
    "EnrichmentProgressRepository",
    "MAX_ASPECT_COUNT",
    "build_efficacy_snapshot",
    "build_failure_terminal_result",
    "select_operational_limitation",
]
