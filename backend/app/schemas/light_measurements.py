from datetime import datetime
from enum import StrEnum
from uuid import UUID

from app.schemas.common import ApiSchema


class LightClassification(StrEnum):
    baja = "baja"
    media = "media"
    alta = "alta"
    directa = "directa"


class MeasurementReliability(StrEnum):
    high = "high"
    medium = "medium"
    low = "low"


class LightMeasurementDto(ApiSchema):
    id: UUID
    user_id: UUID
    garden_plant_id: UUID | None = None
    classification: LightClassification
    lux: float | None = None
    reliability: MeasurementReliability
    measured_at: datetime
