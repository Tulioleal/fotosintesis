from datetime import datetime
from uuid import UUID

from app.schemas.common import ApiSchema


class AssistantSource(ApiSchema):
    title: str | None = None
    url: str
    domain: str | None = None
    confidence: float | None = None


class AssistantMessage(ApiSchema):
    role: str
    content: str
    created_at: datetime | None = None


class AssistantChatRequest(ApiSchema):
    message: str
    conversation_id: UUID | None = None
    plant: str | None = None


class AssistantChatResponse(ApiSchema):
    conversation_id: UUID
    message: AssistantMessage
    sources: list[AssistantSource] = []
    requires_confirmation: bool = False
    tool_failures: list[str] = []
