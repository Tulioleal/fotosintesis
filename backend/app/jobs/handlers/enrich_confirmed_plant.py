from __future__ import annotations

from pydantic import BaseModel
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.enrichment.policy import get_enrichment_policy
from app.enrichment.service import (
    EnrichmentExecution,
    EnrichmentExecutionService,
    ProductionEnrichmentService,
)
from app.jobs.handler import (
    EnrichmentEfficacySnapshot,
    JobHandler,
    JobHandlerResult,
)
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
    def __init__(
        self,
        service: EnrichmentExecutionService | None = None,
        *,
        policy_resolver=get_enrichment_policy,
    ) -> None:
        self._service = service or ProductionEnrichmentService()
        self._policy_resolver = policy_resolver

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
            policy = self._policy_resolver(payload.policy_version)
        except ValueError:
            return JobHandlerResult.failed(
                category=JobFailureCategory.unsupported_payload_version,
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
                efficacy=self._zero_snapshot(payload.policy_version),
            )
        except DBAPIError:
            return JobHandlerResult.failed(
                category=JobFailureCategory.database_transient,
                retryable=True,
                efficacy=self._zero_snapshot(payload.policy_version),
            )
        except VectorIndexError:
            return JobHandlerResult.failed(
                category=JobFailureCategory.indexing_transient,
                retryable=True,
                efficacy=self._zero_snapshot(payload.policy_version),
            )
        except (ProviderError, AllProvidersFailedError, TimeoutError):
            return JobHandlerResult.failed(
                category=JobFailureCategory.provider_transient,
                retryable=True,
                efficacy=self._zero_snapshot(payload.policy_version),
            )
        except ValueError:
            return JobHandlerResult.failed(
                category=JobFailureCategory.invariant_violation,
                retryable=False,
                efficacy=self._zero_snapshot(payload.policy_version),
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
                efficacy=self._snapshot(
                    payload.policy_version,
                    execution=execution,
                    final_covered_count=0,
                    accepted_aspect_count=0,
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
            return JobHandlerResult(
                status=JobStatus.partial,
                result=result,
                efficacy=self._snapshot(
                    payload.policy_version,
                    execution=execution,
                    final_covered_count=len(covered),
                    accepted_aspect_count=execution.accepted_aspect_count,
                ),
            )
        result = EnrichmentJobResult(
            outcome="complete",
            policy_version=payload.policy_version,
            covered_aspects=covered,
            missing_aspects=[],
            covered_count=len(covered),
            missing_count=0,
            acquisition_avoided=execution.acquisition_avoided,
        )
        return JobHandlerResult(
            status=JobStatus.complete,
            result=result,
            efficacy=self._snapshot(
                payload.policy_version,
                execution=execution,
                final_covered_count=len(covered),
                accepted_aspect_count=execution.accepted_aspect_count,
            ),
        )

    @staticmethod
    def _snapshot(
        policy_version: int,
        *,
        execution: EnrichmentExecution,
        final_covered_count: int,
        accepted_aspect_count: int,
    ) -> EnrichmentEfficacySnapshot:
        return EnrichmentEfficacySnapshot(
            policy_version=policy_version,
            acquisition_avoided=execution.acquisition_avoided,
            local_covered_count=execution.local_covered_count,
            final_covered_count=final_covered_count,
            coverage_gain=final_covered_count - execution.local_covered_count,
            accepted_aspect_count=accepted_aspect_count,
            search_count=execution.search_count,
        )

    @staticmethod
    def _zero_snapshot(policy_version: int) -> EnrichmentEfficacySnapshot:
        return EnrichmentEfficacySnapshot(
            policy_version=policy_version,
            acquisition_avoided=False,
            local_covered_count=0,
            final_covered_count=0,
            coverage_gain=0,
            accepted_aspect_count=0,
            search_count=0,
        )


__all__ = ["EnrichConfirmedPlantHandler"]
