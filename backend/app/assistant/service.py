from uuid import UUID
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.assistant.graph import AssistantGraph
from app.assistant.repository import AssistantRepository
from app.assistant.schemas import AssistantChatRequest, AssistantChatResponse, AssistantMessage, AssistantSource
from app.assistant.tools import AssistantTools
from app.knowledge.repository import KnowledgeRepository

logger = logging.getLogger(__name__)


class AssistantService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = AssistantRepository(session)
        self.tools = AssistantTools(self.repository, KnowledgeRepository(session))
        self.graph = AssistantGraph(self.tools)

    async def chat(self, *, user_id: UUID, payload: AssistantChatRequest) -> AssistantChatResponse:
        conversation_id = await self.repository.get_or_create_conversation(
            user_id=user_id,
            conversation_id=payload.conversation_id,
            title=payload.message[:80],
        )
        await self.repository.add_message(
            conversation_id=conversation_id,
            role="user",
            content=payload.message,
            metadata={"plant": payload.plant} if payload.plant else {},
        )
        state = await self.graph.run(
            user_id=user_id,
            message=payload.message,
            plant_hint=payload.plant,
        )
        answer = state.get("answer") or "No pude generar una respuesta segura. Intenta con mas detalles."
        if state.get("tool_failures"):
            logger.warning(
                "assistant_tool_failure",
                extra={"conversation_id": str(conversation_id), "failures": state.get("tool_failures", [])},
            )
        await self.repository.add_message(
            conversation_id=conversation_id,
            role="assistant",
            content=answer,
            metadata={"sources": state.get("sources", []), "tool_failures": state.get("tool_failures", [])},
        )
        return AssistantChatResponse(
            conversation_id=conversation_id,
            message=AssistantMessage(role="assistant", content=answer),
            sources=[AssistantSource.model_validate(source) for source in state.get("sources", [])],
            requires_confirmation=bool(state.get("requires_confirmation")),
            reminder_suggestion=state.get("reminder_suggestion"),
            tool_failures=state.get("tool_failures", []),
        )
