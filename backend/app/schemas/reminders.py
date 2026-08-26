from __future__ import annotations

from datetime import date as Date
from datetime import datetime, time as Time
from enum import Enum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, field_validator
from pydantic import Tag

from app.schemas.common import ApiSchema
from app.scheduling.timezone import resolve_timezone


class ReminderStatus(str, Enum):
    pending = "pending"
    completed = "completed"
    cancelled = "cancelled"


class ReminderRecurrence(str, Enum):
    none = "none"
    daily = "daily"
    weekly = "weekly"
    monthly = "monthly"


class ReminderBase(ApiSchema):
    garden_plant_id: UUID
    action: str = Field(min_length=1, max_length=120)
    date: Date
    time: Time
    recurrence: ReminderRecurrence = ReminderRecurrence.none
    suggestion_justification: str | None = Field(default=None, max_length=1000)
    timezone: str | None = None

    @field_validator("action")
    @classmethod
    def validate_action(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Specify a care action.")
        return stripped

    @field_validator("suggestion_justification")
    @classmethod
    def validate_suggestion_justification(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        zone = resolve_timezone(value)
        if zone is None:
            raise ValueError("Provide a valid IANA timezone.")
        return value.strip()


class ReminderCreate(ReminderBase):
    pass


class ReminderUpdate(ApiSchema):
    garden_plant_id: UUID | None = None
    action: str | None = Field(default=None, min_length=1, max_length=120)
    date: Date | None = None
    time: Time | None = None
    recurrence: ReminderRecurrence | None = None
    suggestion_justification: str | None = Field(default=None, max_length=1000)
    timezone: str | None = None

    @field_validator("action")
    @classmethod
    def validate_action(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("Specify a care action.")
        return stripped

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        zone = resolve_timezone(value)
        if zone is None:
            raise ValueError("Provide a valid IANA timezone.")
        return value.strip()


class ReminderDto(ApiSchema):
    id: UUID
    garden_plant_id: UUID
    plant_name: str
    action: str
    due_at: datetime
    recurrence: ReminderRecurrence
    status: ReminderStatus
    suggestion_justification: str | None = None
    timezone: str | None = None
    next_occurrence_at: datetime | None = None


class ReminderDeleteResponse(ApiSchema):
    status: str


class ReminderSuggestionRequest(ApiSchema):
    garden_plant_id: UUID
    request: str | None = Field(default=None, max_length=2000)


class ReminderSuggestionMetricRequest(ApiSchema):
    outcome: Literal["accepted", "edited", "rejected"]


class ReminderSuggestionEvidence(ApiSchema):
    taxonomy: str | None = None
    location: str | None = None
    notes: str | None = None
    profile_sections: list[str] = Field(default_factory=list)
    active_reminders: int = 0
    light_context: str | None = None


class ReminderSuggestionResult(ApiSchema):
    kind: Literal["suggestion"] = "suggestion"
    garden_plant_id: UUID
    plant_name: str
    action: str
    date: Date
    time: Time
    timezone: str | None = None
    recurrence: ReminderRecurrence
    evidence: ReminderSuggestionEvidence
    confidence: float = Field(ge=0, le=1)
    limitations: list[str] = Field(default_factory=list)
    justification: str


class ReminderClarificationResult(ApiSchema):
    kind: Literal["clarification"] = "clarification"
    missing_fields: list[str]


class ReminderDuplicateResult(ApiSchema):
    kind: Literal["duplicate"] = "duplicate"
    existing_reminder_id: UUID


ReminderSuggestionOutcome = Annotated[
    Annotated[ReminderSuggestionResult, Tag("suggestion")]
    | Annotated[ReminderClarificationResult, Tag("clarification")]
    | Annotated[ReminderDuplicateResult, Tag("duplicate")],
    Field(discriminator="kind"),
]
