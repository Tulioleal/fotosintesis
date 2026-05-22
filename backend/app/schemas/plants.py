from uuid import UUID

from app.schemas.common import ApiSchema


class PlantDto(ApiSchema):
    id: UUID
    scientific_name: str
    common_name: str | None = None
    gbif_key: str | None = None
    family: str | None = None
    genus: str | None = None
    species: str | None = None
