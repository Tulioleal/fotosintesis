from datetime import datetime
from enum import StrEnum
from uuid import UUID

from app.schemas.common import ApiSchema


class ReminderStatus(StrEnum):
    pending = "pending"
    completed = "completed"
    cancelled = "cancelled"


class ReminderDto(ApiSchema):
    id: UUID
    garden_plant_id: UUID
    action: str
    due_at: datetime
    recurrence: str | None = None
    status: ReminderStatus
    suggestion_justification: str | None = None
