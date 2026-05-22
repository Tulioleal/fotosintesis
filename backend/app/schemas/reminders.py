from datetime import datetime
from enum import Enum
from uuid import UUID

from app.schemas.common import ApiSchema


class ReminderStatus(str, Enum):
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
