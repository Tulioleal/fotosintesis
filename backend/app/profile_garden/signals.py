"""Transactional evidence-change signals for profile refresh.

After accepted enrichment evidence commits for a composite species, the system
records an evidence-change signal (a durable ``refresh_profile`` job) for that
species and the changed canonical aspects in the same transaction. The signal
carries only species identity, changed aspects, and a deterministic evidence
fingerprint — never raw evidence content or job payload internals.
"""

from __future__ import annotations

import hashlib
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.enrichment.identity import CanonicalSpeciesIdentity
from app.jobs.repository import EnqueueResult, JobRepository
from app.jobs.schemas import (
    JobPayloadVersion,
    JobType,
    RefreshProfilePayload,
)
from app.profile_garden.fingerprint import compute_evidence_fingerprint


def profile_refresh_idempotency_key(*, species_key: str, fingerprint: str) -> str:
    """Collapse duplicate refresh signals for the same evidence state.

    Because the fingerprint is deterministic for a given accepted evidence
    set, repeated acquisitions that change the same evidence produce the same
    key and collapse into one refresh rather than duplicate active versions.
    """
    raw = f"profile-refresh:{species_key}:{fingerprint}"
    return hashlib.sha256(raw.encode()).hexdigest()


async def enqueue_profile_refresh(
    session: AsyncSession,
    *,
    identity: CanonicalSpeciesIdentity,
    changed_aspects: list[str],
    generation_policy_version: int,
    evidence: list[dict[str, object]],
    caused_by_enrichment_job_id: UUID | None = None,
) -> EnqueueResult:
    """Enqueue a durable refresh job for the affected species sections.

    The job is enqueued in the caller's transaction so the signal is
    transactional with the accepted-ingestion commit. ``evidence`` items must
    expose ``source_url`` and ``source_version`` to derive the fingerprint.
    When ``caused_by_enrichment_job_id`` is provided, a durable association
    between the refresh and its causing enrichment run is recorded in the same
    transaction; legacy reconciliation passes ``None`` and creates no
    association.
    """
    fingerprint = compute_evidence_fingerprint(
        evidence=evidence,
        generation_policy_version=generation_policy_version,
    )
    payload = RefreshProfilePayload(
        policy_version=generation_policy_version,
        species={
            "accepted_gbif_key": identity.accepted_gbif_key,
            "normalized_binomial": identity.normalized_binomial,
        },
        changed_aspects=sorted(set(changed_aspects)),
        fingerprint=fingerprint,
        run_id=uuid4(),
    )
    repository = JobRepository(session)
    result = await repository.enqueue_result(
        job_type=JobType.refresh_profile.value,
        payload_version=JobPayloadVersion.REFRESH_PROFILE_V1,
        payload=payload.model_dump(mode="json"),
        idempotency_key=profile_refresh_idempotency_key(
            species_key=identity.key,
            fingerprint=fingerprint,
        ),
        max_attempts=3,
    )

    if caused_by_enrichment_job_id is not None:
        await repository.associate_profile_refresh(
            refresh_job_id=result.job_id,
            enrichment_job_id=caused_by_enrichment_job_id,
        )

    return result


__all__ = [
    "enqueue_profile_refresh",
    "profile_refresh_idempotency_key",
]
