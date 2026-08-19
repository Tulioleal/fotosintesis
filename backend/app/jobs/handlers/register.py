from pydantic import BaseModel

from app.jobs.handler import HandlerRegistry, get_handler_registry
from app.jobs.handlers.enrich_confirmed_plant import EnrichConfirmedPlantHandler
from app.jobs.handlers.ingest_validated_claims import IngestValidatedClaimsHandler
from app.jobs.handlers.refresh_profile import RefreshProfileHandler
from app.jobs.schemas import (
    EnrichConfirmedPlantPayload,
    IngestValidatedClaimsPayload,
    JobPayloadVersion,
    JobType,
    RefreshProfilePayload,
)

PRODUCTION_PAYLOAD_MODELS: dict[str, dict[int, type[BaseModel]]] = {
    JobType.ingest_validated_claims.value: {
        JobPayloadVersion.INGEST_VALIDATED_CLAIMS_V1: IngestValidatedClaimsPayload,
    },
    JobType.enrich_confirmed_plant.value: {
        JobPayloadVersion.ENRICH_CONFIRMED_PLANT_V1: EnrichConfirmedPlantPayload,
    },
    JobType.refresh_profile.value: {
        JobPayloadVersion.REFRESH_PROFILE_V1: RefreshProfilePayload,
    },
}


def get_production_payload_model(
    job_type: str,
    payload_version: int,
) -> type[BaseModel] | None:
    """Resolve a production payload model without constructing handlers."""
    return PRODUCTION_PAYLOAD_MODELS.get(job_type, {}).get(payload_version)


def register_handlers(registry: HandlerRegistry | None = None) -> None:
    """Register missing global production handlers into the target registry.

    Construction is idempotent: handlers already present for a job type are
    left untouched so retries and explicit registries never conflict. The
    payload models come from the same static catalog a disabled worker uses to
    validate required contracts without constructing handlers.
    """
    target = registry or get_handler_registry()
    if not target.has_handler(JobType.ingest_validated_claims.value):
        target.register(
            JobType.ingest_validated_claims.value,
            IngestValidatedClaimsHandler(),
            payload_models=PRODUCTION_PAYLOAD_MODELS[
                JobType.ingest_validated_claims.value
            ],
        )
    if not target.has_handler(JobType.enrich_confirmed_plant.value):
        target.register(
            JobType.enrich_confirmed_plant.value,
            EnrichConfirmedPlantHandler(),
            payload_models=PRODUCTION_PAYLOAD_MODELS[
                JobType.enrich_confirmed_plant.value
            ],
        )
    if not target.has_handler(JobType.refresh_profile.value):
        target.register(
            JobType.refresh_profile.value,
            RefreshProfileHandler(),
            payload_models=PRODUCTION_PAYLOAD_MODELS[
                JobType.refresh_profile.value
            ],
        )
