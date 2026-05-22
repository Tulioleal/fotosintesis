from datetime import datetime
from enum import Enum
from uuid import UUID

from app.schemas.common import ApiSchema


class MessageRole(str, Enum):
    user = "user"
    assistant = "assistant"
    system = "system"
    tool = "tool"


class ConversationDto(ApiSchema):
    id: UUID
    user_id: UUID
    title: str | None = None
    created_at: datetime


class ConversationMessageDto(ApiSchema):
    id: UUID
    conversation_id: UUID
    role: MessageRole
    content: str
    created_at: datetime
