from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from app.schemas.common import ApiSchema
from app.schemas.reminders import ReminderRecurrence


AssistantMessageContentFormat = Literal["plain_text", "markdown"]
SourceProvenance = Literal["trusted", "external_fallback"]
DEFAULT_ASSISTANT_MESSAGE_CONTENT_FORMAT: AssistantMessageContentFormat = "plain_text"


class AssistantSource(ApiSchema):
    title: str | None = None
    url: str
    domain: str | None = None
    confidence: float | None = None
    source_provenance: SourceProvenance | None = None


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
    answerability_status: str | None = None
    contradictions: list[dict] = []
    provider_fallbacks: list[dict] | None = None
    llm_general_guidance_used: bool = False


class AssistantReminderSuggestion(ApiSchema):
    garden_plant_id: UUID
    plant_name: str
    action: str
    due_at: datetime
    recurrence: ReminderRecurrence
    suggestion_justification: str
    timezone: str | None = None
    # Explicit local schedule fields so clients never reconstruct date/time by
    # slicing the due_at instant.
    date: str | None = None
    time: str | None = None
    # Evidence-grounding parity with page-flow suggestions.
    confidence: float | None = None
    limitations: list[str] = Field(default_factory=list)
    evidence: dict[str, object] | None = None


class AssistantChatRequest(ApiSchema):
    message: str
    conversation_id: UUID | None = None
    plant: str | None = None
    plant_binomial_name: str | None = None
    plant_scientific_name: str | None = None
    confirmed_candidate_id: UUID | None = None


class AssistantChatResponse(ApiSchema):
    conversation_id: UUID
    message: AssistantMessage
    sources: list[AssistantSource] = []
    requires_confirmation: bool = False
    reminder_suggestion: AssistantReminderSuggestion | None = None
    tool_failures: list[str] = []
    diagnostics: AssistantCareDiagnostics | None = None


class ProviderFailureDetail(ApiSchema):
    provider: str = ""
    role: str = ""
    operation: str = ""
    failure_category: str | None = None
    retryable: bool = False
    transient: bool = False
    status_code: int | None = None
    cause_type: str | None = None
    attempt_index: int | None = None


class AssistantRetryableError(ApiSchema):
    retryable: bool = True
    error_type: str = "total_generation_failure"
    detail: str = "No model-generated assistant response could be produced. Please retry."
    failure_category: str | None = None
    provider_failures: list[ProviderFailureDetail] = []
    conversation_id: UUID | None = None
