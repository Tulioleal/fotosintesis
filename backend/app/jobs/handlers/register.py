from app.jobs.handler import get_handler_registry
from app.jobs.handlers.enrich_confirmed_plant import EnrichConfirmedPlantHandler
from app.jobs.handlers.ingest_validated_claims import IngestValidatedClaimsHandler
from app.jobs.schemas import (
    EnrichConfirmedPlantPayload,
    IngestValidatedClaimsPayload,
    JobPayloadVersion,
    JobType,
)


def register_handlers() -> None:
    registry = get_handler_registry()
    registry.register(
        JobType.ingest_validated_claims.value,
        IngestValidatedClaimsHandler(),
        payload_models={
            JobPayloadVersion.INGEST_VALIDATED_CLAIMS_V1:
                IngestValidatedClaimsPayload,
        },
    )
    registry.register(
        JobType.enrich_confirmed_plant.value,
        EnrichConfirmedPlantHandler(),
        payload_models={
            JobPayloadVersion.ENRICH_CONFIRMED_PLANT_V1:
                EnrichConfirmedPlantPayload,
        },
    )
