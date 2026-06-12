from datetime import datetime
from typing import Literal
from uuid import UUID

from app.schemas.common import ApiSchema
from app.schemas.reminders import ReminderRecurrence


AssistantMessageContentFormat = Literal["plain_text", "markdown"]
DEFAULT_ASSISTANT_MESSAGE_CONTENT_FORMAT: AssistantMessageContentFormat = "plain_text"


class AssistantSource(ApiSchema):
    title: str | None = None
    url: str
    domain: str | None = None
    confidence: float | None = None


class AssistantMessage(ApiSchema):
    role: str
    content: str
    content_format: AssistantMessageContentFormat = DEFAULT_ASSISTANT_MESSAGE_CONTENT_FORMAT
    created_at: datetime | None = None


class AssistantCareDiagnostics(ApiSchema):
    intent: str | None = None
    topic: str | None = None
    required_aspects: list[str] = []
    covered_aspects: list[str] = []
    missing_aspects: list[str] = []
    evidence_path: list[str] = []
    answer_language: str | None = None


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
    plant_binomial_name: str | None = None
    plant_scientific_name: str | None = None


class AssistantChatResponse(ApiSchema):
    conversation_id: UUID
    message: AssistantMessage
    sources: list[AssistantSource] = []
    requires_confirmation: bool = False
    reminder_suggestion: AssistantReminderSuggestion | None = None
    tool_failures: list[str] = []
    diagnostics: AssistantCareDiagnostics | None = None
