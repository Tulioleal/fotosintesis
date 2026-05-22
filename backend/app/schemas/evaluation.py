from datetime import datetime
from enum import Enum
from uuid import UUID

from app.schemas.common import ApiSchema


class EvaluationRunStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class EvaluationRunDto(ApiSchema):
    id: UUID
    status: EvaluationRunStatus
    started_at: datetime
    completed_at: datetime | None = None
