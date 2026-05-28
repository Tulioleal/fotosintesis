from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ProfileAlias(BaseModel):
    name: str
    region: str | None = None
    country: str | None = None
    language: str | None = None


class ProfileSource(BaseModel):
    title: str
    url: str
    domain: str
    confidence: float


class PlantProfileResponse(BaseModel):
    id: UUID
    scientific_name: str
    common_name: str | None = None
    selected_alias: str | None = None
    aliases: list[ProfileAlias] = Field(default_factory=list)
    sections: dict[str, list[str]] = Field(default_factory=dict)
    sources: list[ProfileSource] = Field(default_factory=list)
    confidence: float
    limitations: list[str] = Field(default_factory=list)


class GardenPlantCreate(BaseModel):
    confirmed_candidate_id: UUID
    nickname: str | None = None
    notes: str | None = None
    location: str | None = None
    image_path: str | None = None
    custom_data: dict[str, object] = Field(default_factory=dict)


class GardenPlantUpdate(BaseModel):
    nickname: str | None = None
    notes: str | None = None
    location: str | None = None
    image_path: str | None = None
    custom_data: dict[str, object] = Field(default_factory=dict)


class GardenPlantResponse(BaseModel):
    id: UUID
    profile: PlantProfileResponse
    confirmed_candidate_id: UUID | None = None
    nickname: str | None = None
    notes: str | None = None
    location: str | None = None
    image_path: str | None = None
    custom_data: dict[str, object] = Field(default_factory=dict)
    active_reminders: int = 0
    created_at: datetime


class GardenDeleteResponse(BaseModel):
    status: str
