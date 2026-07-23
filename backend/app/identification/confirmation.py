from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings, get_settings
from app.enrichment import (
    CanonicalSpeciesIdentity,
    build_active_work_key,
    build_run_idempotency_key,
    get_current_enrichment_policy,
)
from app.identification.repository import IdentificationRepository
from app.identification.schemas import ConfirmationResponse
from app.jobs.repository import JobRepository
from app.jobs.schemas import EnrichConfirmedPlantPayload, JobPayloadVersion, JobType
from app.observability.metrics import metrics_registry

logger = logging.getLogger(__name__)


class ConfirmationRejectedError(ValueError):
    pass


class ConfirmationSchedulingUnavailable(RuntimeError):
    pass


class CandidateConfirmationService:
    def __init__(self, session: AsyncSession, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.identifications = IdentificationRepository(session)
        self.jobs = JobRepository(session, self.settings)

    async def confirm(
        self, *, identification_id: UUID, candidate_id: UUID, user_id: UUID
    ) -> ConfirmationResponse:
        if not self.settings.jobs_producer_enabled:
            await self.session.rollback()
            raise ConfirmationSchedulingUnavailable("durable scheduling is disabled")

        candidate = await self.identifications.confirm_candidate(
            identification_id=identification_id,
            candidate_id=candidate_id,
            user_id=user_id,
        )
        if candidate is None:
            await self.session.rollback()
            raise ConfirmationRejectedError

        try:
            identity = CanonicalSpeciesIdentity(
                accepted_gbif_key=candidate.gbif_accepted_key,
                normalized_binomial=candidate.binomial_name,
                taxonomy_validated=candidate.validation_status.value == "validated",
            )
            if identity.normalized_binomial is None:
                raise ValueError("confirmed enrichment requires a validated binomial")
        except ValueError as exc:
            await self.session.rollback()
            raise ConfirmationRejectedError from exc

        snapshot = {
            "gbif_key": candidate.gbif_key,
            "accepted_gbif_key": candidate.gbif_accepted_key,
            "accepted_scientific_name": candidate.accepted_scientific_name,
            "normalized_binomial": identity.normalized_binomial,
            "taxonomic_status": candidate.taxonomic_status,
            "synonyms": candidate.synonyms,
            "genus": candidate.genus,
            "family": candidate.family,
            "species": candidate.species,
        }
        source_version = hashlib.sha256(
            json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        policy = get_current_enrichment_policy()
        run_id = uuid4()

        try:
            taxonomy_provenance_id = (
                await self.identifications.create_or_reuse_taxonomy_snapshot(
                    identity=identity,
                    source_version=source_version,
                    snapshot=snapshot,
                    resolved_at=datetime.now(timezone.utc),
                )
            )
            payload = EnrichConfirmedPlantPayload(
                policy_version=policy.version,
                species={
                    "accepted_gbif_key": identity.accepted_gbif_key,
                    "normalized_binomial": identity.normalized_binomial,
                },
                taxonomy_provenance_id=taxonomy_provenance_id,
                run_id=run_id,
            )
            association = await self.jobs.associate_candidate_enrichment(
                candidate_id=candidate_id,
                user_id=user_id,
                policy_version=policy.version,
                payload_version=JobPayloadVersion.ENRICH_CONFIRMED_PLANT_V1,
                payload=payload.model_dump(mode="json"),
                idempotency_key=build_run_idempotency_key(identity, policy.version, run_id),
                active_deduplication_key=build_active_work_key(identity, policy.version),
                max_attempts=policy.max_durable_attempts,
            )
            enrichment = await self.jobs.get_candidate_enrichment_status(
                candidate_id=candidate_id,
                user_id=user_id,
                policy_version=policy.version,
            )
            if enrichment is None:
                raise RuntimeError("candidate enrichment association is not visible")
            await self.session.commit()

            schedule_outcome = (
                "created" if association.job_created else "reused"
            )

            metrics_registry.record_job_schedule(
                job_type=JobType.enrich_confirmed_plant.value,
                outcome=schedule_outcome,
            )

            logger.info(
                "job_scheduled",
                extra={
                    "ctx_job_id": str(association.job_id),
                    "ctx_job_type": JobType.enrich_confirmed_plant.value,
                    "ctx_payload_version": payload.payload_version,
                    "ctx_policy_version": policy.version,
                    "ctx_ownership_category": "shared_species",
                    "ctx_schedule_outcome": schedule_outcome,
                },
            )
        except Exception as exc:
            await self.session.rollback()
            raise ConfirmationSchedulingUnavailable("durable scheduling failed") from exc

        return ConfirmationResponse(
            status="confirmed",
            candidate=candidate,
            enrichment=enrichment,
        )


__all__ = [
    "CandidateConfirmationService",
    "ConfirmationRejectedError",
    "ConfirmationSchedulingUnavailable",
]
