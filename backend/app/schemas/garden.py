from datetime import datetime
from uuid import UUID

from app.schemas.common import ApiSchema


class GardenPlantDto(ApiSchema):
    id: UUID
    user_id: UUID
    plant_id: UUID
    nickname: str | None = None
    image_url: str | None = None
    created_at: datetime
