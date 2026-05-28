from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import Field, field_validator

from app.schemas.common import ApiSchema


class LightClassification(str, Enum):
    baja = "baja"
    media = "media"
    alta = "alta"
    directa = "directa"


class MeasurementReliability(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"


class MeasurementSource(str, Enum):
    sensor = "sensor"
    camera = "camera"
    manual = "manual"


class LightMeasurementCreate(ApiSchema):
    garden_plant_id: UUID | None = None
    classification: LightClassification
    lux: float | None = Field(default=None, ge=0)
    reliability: MeasurementReliability
    source: MeasurementSource
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, object]) -> dict[str, object]:
        return value or {}


class LightMeasurementDto(ApiSchema):
    id: UUID
    user_id: UUID
    garden_plant_id: UUID | None = None
    classification: LightClassification
    lux: float | None = None
    reliability: MeasurementReliability
    source: MeasurementSource
    metadata: dict[str, object]
    measured_at: datetime
