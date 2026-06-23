from uuid import UUID
import asyncio
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
from app.db.session import AsyncSessionLocal
from app.knowledge.repository import KnowledgeRepository

logger = logging.getLogger(__name__)


class AssistantService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = AssistantRepository(session)
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
        _schedule_validated_claim_ingestion(
            claims=list(state.get("ingestion_claims", []) or []),
            conversation_id=conversation_id,
            answerability_status=str(state.get("answerability_status") or ""),
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


def _schedule_validated_claim_ingestion(
    *, claims: list[dict], conversation_id: UUID, answerability_status: str
) -> None:
    if not claims:
        return
    # Best-effort in-process background work; a process exit can drop this ingestion.
    asyncio.create_task(
        _ingest_validated_claims_background(
            claims=claims,
            conversation_id=conversation_id,
            answerability_status=answerability_status,
        )
    )


async def _ingest_validated_claims_background(
    *, claims: list[dict], conversation_id: UUID, answerability_status: str
) -> None:
    claim_context = _validated_claim_log_context(claims)
    async with AsyncSessionLocal() as session:
        tools = AssistantTools(AssistantRepository(session), KnowledgeRepository(session))
        try:
            result = await tools.ingest_validated_claims(claims)
            if not result.ok:
                await session.rollback()
                logger.warning(
                    "assistant_validated_claim_ingestion_failed",
                    extra={
                        "conversation_id": str(conversation_id),
                        "answerability_status": answerability_status,
                        **claim_context,
                        "error": result.error,
                    },
                )
                return
            await session.commit()
        except Exception:
            await session.rollback()
            logger.exception(
                "assistant_validated_claim_ingestion_exception",
                extra={
                    "conversation_id": str(conversation_id),
                    "answerability_status": answerability_status,
                    **claim_context,
                },
            )


def _validated_claim_log_context(claims: list[dict]) -> dict[str, object]:
    return {
        "claim_count": len(claims),
        "scientific_names": _unique_claim_values(claims, "scientific_name"),
        "source_urls": _unique_claim_values(claims, "source_url"),
        "source_domains": _unique_claim_values(claims, "source_domain"),
    }


def _unique_claim_values(claims: list[dict], key: str, *, limit: int = 3) -> list[str]:
    values: list[str] = []
    seen: set[str] = set()
    for claim in claims:
        value = str(claim.get(key) or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        values.append(value)
        if len(values) >= limit:
            break
    return values
