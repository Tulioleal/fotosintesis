from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ApiSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class TimestampedSchema(ApiSchema):
    created_at: datetime


class IdentifiedSchema(ApiSchema):
    id: UUID
