from __future__ import annotations

from datetime import date as Date
from datetime import datetime, time as Time
from enum import Enum
from uuid import UUID

from pydantic import Field, field_validator

from app.schemas.common import ApiSchema


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

    @field_validator("action")
    @classmethod
    def validate_action(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Indica una accion de cuidado.")
        return stripped

    @field_validator("suggestion_justification")
    @classmethod
    def validate_suggestion_justification(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class ReminderCreate(ReminderBase):
    pass


class ReminderUpdate(ApiSchema):
    garden_plant_id: UUID | None = None
    action: str | None = Field(default=None, min_length=1, max_length=120)
    date: Date | None = None
    time: Time | None = None
    recurrence: ReminderRecurrence | None = None
    suggestion_justification: str | None = Field(default=None, max_length=1000)

    @field_validator("action")
    @classmethod
    def validate_action(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("Indica una accion de cuidado.")
        return stripped


class ReminderDto(ApiSchema):
    id: UUID
    garden_plant_id: UUID
    plant_name: str
    action: str
    due_at: datetime
    recurrence: ReminderRecurrence
    status: ReminderStatus
    suggestion_justification: str | None = None
    next_occurrence_at: datetime | None = None


class ReminderDeleteResponse(ApiSchema):
    status: str
