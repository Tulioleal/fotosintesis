from datetime import datetime
from uuid import UUID

from app.schemas.common import ApiSchema
from app.schemas.reminders import ReminderRecurrence


class AssistantSource(ApiSchema):
    title: str | None = None
    url: str
    domain: str | None = None
    confidence: float | None = None


class AssistantMessage(ApiSchema):
    role: str
    content: str
    created_at: datetime | None = None


class AssistantReminderSuggestion(ApiSchema):
    garden_plant_id: UUID
    plant_name: str
    action: str
    due_at: datetime
    recurrence: ReminderRecurrence
    suggestion_justification: str


class AssistantChatRequest(ApiSchema):
    message: str
    conversation_id: UUID | None = None
    plant: str | None = None


class AssistantChatResponse(ApiSchema):
    conversation_id: UUID
    message: AssistantMessage
    sources: list[AssistantSource] = []
    requires_confirmation: bool = False
    reminder_suggestion: AssistantReminderSuggestion | None = None
    tool_failures: list[str] = []
