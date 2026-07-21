from app.jobs.handler import get_handler_registry
from app.jobs.handlers.ingest_validated_claims import IngestValidatedClaimsHandler
from app.jobs.schemas import IngestValidatedClaimsPayload, JobPayloadVersion, JobType


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
