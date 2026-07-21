from uuid import UUID

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.assistant.graph import AssistantGraph, _diagnostics, display_plant_name, operational_plant_name
from app.assistant.repository import AssistantRepository
from app.assistant.schemas import (
    DEFAULT_ASSISTANT_MESSAGE_CONTENT_FORMAT,
    AssistantChatRequest,
    AssistantChatResponse,
    AssistantCareDiagnostics,
    AssistantMessage,
    AssistantRetryableError,
    AssistantSource,
    ProviderFailureDetail,
)
from app.assistant.tools import AssistantTools
from app.jobs.repository import JobRepository, canonical_idempotency_key, compute_claims_hash
from app.jobs.schemas import (
    CURRENT_INGESTION_POLICY_VERSION,
    IngestValidatedClaimsPayload,
    JobPayloadVersion,
    JobType,
)
from app.knowledge.repository import KnowledgeRepository
from app.observability.metrics import metrics_registry

logger = logging.getLogger(__name__)


class AssistantService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = AssistantRepository(session)
        self.job_repo = JobRepository(session)
        self.tools = AssistantTools(self.repository, KnowledgeRepository(session))
        self.graph = AssistantGraph(self.tools)

    async def chat(
        self, *, user_id: UUID, payload: AssistantChatRequest
    ) -> AssistantChatResponse | AssistantRetryableError:
        operation_name = operational_plant_name(
            plant=payload.plant,
            plant_binomial_name=payload.plant_binomial_name,
            plant_scientific_name=payload.plant_scientific_name,
        )
        display_name = display_plant_name(
            plant=payload.plant,
            plant_binomial_name=payload.plant_binomial_name,
            plant_scientific_name=payload.plant_scientific_name,
        )
        plant_metadata = {
            key: value
            for key, value in {
                "plant": payload.plant,
                "plant_binomial_name": payload.plant_binomial_name,
                "plant_scientific_name": payload.plant_scientific_name,
                "operational_plant_name": operation_name,
                "display_plant_name": display_name,
            }.items()
            if value
        }
        conversation_id = await self.repository.get_or_create_conversation(
            user_id=user_id,
            conversation_id=payload.conversation_id,
            title=payload.message[:80],
        )
        await self.repository.add_message(
            conversation_id=conversation_id,
            role="user",
            content=payload.message,
            metadata=plant_metadata,
        )
        state = await self.graph.run(
            user_id=user_id,
            message=payload.message,
            plant_hint=payload.plant,
            plant_binomial_name=payload.plant_binomial_name,
            plant_scientific_name=payload.plant_scientific_name,
        )
        if state.get("total_generation_failure") and not state.get("answer"):
            tool_failures = state.get("tool_failures", [])
            if tool_failures:
                logger.warning(
                    "assistant_total_generation_failure",
                    extra={
                        "conversation_id": str(conversation_id),
                        "failures": tool_failures,
                    },
                )
            gen_failure = state.get("generation_failure")
            failure_category = gen_failure.failure_category if gen_failure else None
            provider_failures = [
                ProviderFailureDetail(
                    provider=entry.provider,
                    role=entry.role,
                    operation=entry.operation,
                    failure_category=entry.failure_category,
                    retryable=entry.retryable,
                    transient=entry.transient,
                    status_code=entry.status_code,
                    cause_type=entry.cause_type,
                    attempt_index=entry.attempt_index,
                )
                for entry in (gen_failure.provider_failures if gen_failure else [])
            ]
            return AssistantRetryableError(
                failure_category=failure_category,
                provider_failures=provider_failures[:5],
                conversation_id=conversation_id,
            )
        answer = state.get("answer") or ""
        diagnostics = state.get("diagnostics") or _diagnostics(state)
        if state.get("tool_failures"):
            logger.warning(
                "assistant_tool_failure",
                extra={"conversation_id": str(conversation_id), "failures": state.get("tool_failures", [])},
            )
        await self.repository.add_message(
            conversation_id=conversation_id,
            role="assistant",
            content=answer,
            metadata={
                "content_format": DEFAULT_ASSISTANT_MESSAGE_CONTENT_FORMAT,
                "sources": state.get("sources", []),
                "tool_failures": state.get("tool_failures", []),
                "fallback_reasons": state.get("fallback_reasons", []),
                "provider_fallbacks": state.get("provider_fallbacks", []),
                "diagnostics": diagnostics,
            },
        )

        claims = list(state.get("ingestion_claims", []) or [])
        enqueue_result = None
        if claims and self._should_enqueue_ingestion_jobs():
            job_payload = IngestValidatedClaimsPayload.model_validate(
                {
                    "payload_version":
                        JobPayloadVersion.INGEST_VALIDATED_CLAIMS_V1,
                    "ingestion_policy_version":
                        CURRENT_INGESTION_POLICY_VERSION,
                    "claims": claims,
                    "conversation_id": str(conversation_id),
                    "answerability_status": state.get("answerability_status"),
                }
            )
            serialized_payload = job_payload.model_dump(mode="json")
            claims_hash = compute_claims_hash(serialized_payload["claims"])
            idempotency_key = canonical_idempotency_key(
                job_type=JobType.ingest_validated_claims.value,
                conversation_id=conversation_id,
                claims_hash=claims_hash,
                payload_version=job_payload.payload_version,
                ingestion_policy_version=job_payload.ingestion_policy_version,
            )
            enqueue_result = await self.job_repo.enqueue_result(
                job_type=JobType.ingest_validated_claims.value,
                payload_version=job_payload.payload_version,
                payload=serialized_payload,
                idempotency_key=idempotency_key,
                user_id=user_id,
                conversation_id=conversation_id,
            )

        await self.repository.commit()
        if enqueue_result is not None:
            schedule_outcome = "created" if enqueue_result.created else "reused"
            metrics_registry.record_job_schedule(
                job_type=JobType.ingest_validated_claims.value,
                outcome=schedule_outcome,
            )
            logger.info(
                "job_scheduled",
                extra={
                    "ctx_job_id": str(enqueue_result.job_id),
                    "ctx_job_type": JobType.ingest_validated_claims.value,
                    "ctx_payload_version": job_payload.payload_version,
                    "ctx_ownership_category": "user_owned",
                    "ctx_schedule_outcome": schedule_outcome,
                    "ctx_conversation_id": str(conversation_id),
                },
            )
        return AssistantChatResponse(
            conversation_id=conversation_id,
            message=AssistantMessage(
                role="assistant",
                content=answer,
                content_format=DEFAULT_ASSISTANT_MESSAGE_CONTENT_FORMAT,
            ),
            sources=[AssistantSource.model_validate(source) for source in state.get("sources", [])],
            requires_confirmation=bool(state.get("requires_confirmation")),
            reminder_suggestion=state.get("reminder_suggestion"),
            tool_failures=state.get("tool_failures", []),
            diagnostics=AssistantCareDiagnostics.model_validate(diagnostics) if diagnostics else None,
        )

    @staticmethod
    def _should_enqueue_ingestion_jobs() -> bool:
        from app.core.settings import get_settings
        return get_settings().jobs_producer_enabled
