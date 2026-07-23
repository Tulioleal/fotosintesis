from __future__ import annotations

from pydantic import BaseModel
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.enrichment.policy import get_enrichment_policy
from app.enrichment.service import (
    EnrichmentExecutionService,
    ProductionEnrichmentService,
)
from app.jobs.handler import JobHandler, JobHandlerResult
from app.jobs.schemas import (
    EnrichConfirmedPlantPayload,
    EnrichmentJobResult,
    EnrichmentLimitation,
    JobError,
    JobFailureCategory,
    JobStatus,
)
from app.knowledge.rag import VectorIndexError
from app.providers.errors import ProviderError
from app.providers.wrappers import AllProvidersFailedError


class EnrichConfirmedPlantHandler(JobHandler):
    def __init__(self, service: EnrichmentExecutionService | None = None) -> None:
        self._service = service or ProductionEnrichmentService()

    async def handle(
        self,
        *,
        payload: BaseModel,
        attempt_count: int,
        max_attempts: int,
    ) -> JobHandlerResult:
        if not isinstance(payload, EnrichConfirmedPlantPayload):
            return JobHandlerResult.failed(
                category=JobFailureCategory.invalid_payload,
                retryable=False,
            )
        try:
            policy = get_enrichment_policy(payload.policy_version)
        except ValueError:
            return JobHandlerResult.failed(
                category=JobFailureCategory.unsupported_version,
                retryable=False,
            )
        if max_attempts > policy.max_durable_attempts:
            return JobHandlerResult.failed(
                category=JobFailureCategory.invariant_violation,
                retryable=False,
            )
        try:
            execution = await self._service.execute(payload)
        except IntegrityError:
            return JobHandlerResult.failed(
                category=JobFailureCategory.invariant_violation,
                retryable=False,
            )
        except DBAPIError:
            return JobHandlerResult.failed(
                category=JobFailureCategory.database_transient,
                retryable=True,
            )
        except VectorIndexError:
            return JobHandlerResult.failed(
                category=JobFailureCategory.indexing_transient,
                retryable=True,
            )
        except (ProviderError, AllProvidersFailedError, TimeoutError):
            return JobHandlerResult.failed(
                category=JobFailureCategory.provider_transient,
                retryable=True,
            )
        except ValueError:
            return JobHandlerResult.failed(
                category=JobFailureCategory.invariant_violation,
                retryable=False,
            )

        covered = [aspect.value for aspect in execution.covered_aspects]
        missing = [aspect.value for aspect in execution.missing_aspects]
        if not covered:
            return JobHandlerResult(
                status=JobStatus.failed,
                error=JobError(
                    category=JobFailureCategory.insufficient_evidence,
                    retryable=False,
                ),
            )
        if missing:
            limitations = [EnrichmentLimitation.missing_required_aspects]
            if execution.safety_evidence_rejected:
                limitations.append(EnrichmentLimitation.safety_evidence_rejected)
            result = EnrichmentJobResult(
                outcome="partial",
                policy_version=payload.policy_version,
                covered_aspects=covered,
                missing_aspects=missing,
                covered_count=len(covered),
                missing_count=len(missing),
                limitations=limitations,
                acquisition_avoided=execution.acquisition_avoided,
            )
            return JobHandlerResult(status=JobStatus.partial, result=result)
        result = EnrichmentJobResult(
            outcome="complete",
            policy_version=payload.policy_version,
            covered_aspects=covered,
            missing_aspects=[],
            covered_count=len(covered),
            missing_count=0,
            acquisition_avoided=execution.acquisition_avoided,
        )
        return JobHandlerResult(status=JobStatus.complete, result=result)


__all__ = ["EnrichConfirmedPlantHandler"]
