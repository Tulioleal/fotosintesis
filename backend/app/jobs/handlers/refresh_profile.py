"""Durable handler that refreshes stale profile sections from accepted evidence.

The payload identifies a canonical species and the canonical aspects whose
accepted evidence changed. The handler regenerates only the sections mapped to
those aspects and replaces them atomically. A failed refresh keeps the prior
visible sections and surfaces them as stale.
"""

from __future__ import annotations

from pydantic import BaseModel
from sqlalchemy.exc import DBAPIError

from app.db.session import AsyncSessionLocal
from app.enrichment.identity import CanonicalSpeciesIdentity
from app.enrichment.policy import get_enrichment_policy
from app.jobs.handler import JobHandler, JobHandlerResult
from app.jobs.schemas import (
    JobError,
    JobFailureCategory,
    JobStatus,
    ProfileRefreshJobResult,
    RefreshProfilePayload,
)
from app.profile_garden.fingerprint import sections_for_aspects
from app.profile_garden.refresh import ProfileRefreshError, ProfileRefreshService
from app.profile_garden.repository import SECTION_TOPICS


class RefreshProfileHandler(JobHandler):
    def __init__(
        self,
        *,
        session_factory=AsyncSessionLocal,
        policy_resolver=get_enrichment_policy,
    ) -> None:
        self._session_factory = session_factory
        self._policy_resolver = policy_resolver

    async def handle(
        self,
        *,
        payload: BaseModel,
        attempt_count: int,
        max_attempts: int,
    ) -> JobHandlerResult:
        if not isinstance(payload, RefreshProfilePayload):
            return JobHandlerResult.failed(
                category=JobFailureCategory.invalid_payload,
                retryable=False,
            )
        try:
            self._policy_resolver(payload.policy_version)
        except ValueError:
            return JobHandlerResult.failed(
                category=JobFailureCategory.unsupported_payload_version,
                retryable=False,
            )
        try:
            identity = CanonicalSpeciesIdentity(
                accepted_gbif_key=payload.species.accepted_gbif_key,
                normalized_binomial=payload.species.normalized_binomial,
                taxonomy_validated=True,
            )
        except ValueError:
            return JobHandlerResult.failed(
                category=JobFailureCategory.invalid_payload,
                retryable=False,
            )

        species = {
            "canonical_species_key": identity.key,
            "normalized_binomial": identity.normalized_binomial,
        }
        try:
            async with self._session_factory() as session:
                result = await ProfileRefreshService(session).refresh_sections(
                    species=species,
                    changed_aspects=payload.changed_aspects,
                    generation_policy_version=payload.policy_version,
                )
        except ProfileRefreshError:
            return JobHandlerResult(
                status=JobStatus.partial,
                result=ProfileRefreshJobResult(
                    outcome="partial",
                    policy_version=payload.policy_version,
                    regenerated_sections=[],
                    stale_sections=sorted(
                        sections_for_aspects(payload.changed_aspects)
                        & set(SECTION_TOPICS)
                    )[:64],
                    limitations=[],
                ),
                error=JobError(
                    category=JobFailureCategory.insufficient_evidence,
                    retryable=False,
                ),
            )
        except DBAPIError:
            return JobHandlerResult.failed(
                category=JobFailureCategory.database_transient,
                retryable=True,
            )

        regenerated = result["regenerated"]
        if not regenerated:
            return JobHandlerResult(
                status=JobStatus.complete,
                result=ProfileRefreshJobResult(
                    outcome="noop",
                    policy_version=payload.policy_version,
                    regenerated_sections=[],
                    stale_sections=[],
                    limitations=[],
                ),
            )
        return JobHandlerResult(
            status=JobStatus.complete,
            result=ProfileRefreshJobResult(
                outcome="complete",
                policy_version=payload.policy_version,
                regenerated_sections=regenerated,
                stale_sections=[],
                limitations=[],
            ),
        )


__all__ = ["RefreshProfileHandler"]
