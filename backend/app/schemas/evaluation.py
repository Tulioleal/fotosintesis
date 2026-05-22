from datetime import datetime
from enum import StrEnum
from uuid import UUID

from app.schemas.common import ApiSchema


class EvaluationRunStatus(StrEnum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class EvaluationRunDto(ApiSchema):
    id: UUID
    status: EvaluationRunStatus
    started_at: datetime
    completed_at: datetime | None = None
