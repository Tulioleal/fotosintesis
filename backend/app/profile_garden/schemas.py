from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.jobs.schemas import CandidateEnrichmentStatus
from app.schemas.light_measurements import (
    LightClassification,
    MeasurementReliability,
    MeasurementSource,
)


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


class ProfileSectionStatus(BaseModel):
    """Per-section freshness metadata (metadata-only, never raw payloads).

    ``status`` is one of ``current``, ``stale``, ``refreshing``, ``partial``.
    ``generated_at`` is the timestamp of the active section version.
    """

    section: str
    status: str
    policy_version: int | None = None
    generated_at: datetime | None = None


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
    enrichment: CandidateEnrichmentStatus | None = None
    accepted_gbif_key: int | None = None
    binomial_name: str | None = None
    canonical_species_key: str | None = None
    generation_policy_version: int | None = None
    section_status: list[ProfileSectionStatus] = Field(default_factory=list)


class GardenPlantCreate(BaseModel):
    confirmed_candidate_id: UUID
    nickname: str | None = None
    notes: str | None = None
    location: str | None = None
    image_path: str | None = None
    custom_data: dict[str, object] = Field(default_factory=dict)


class ReminderSummary(BaseModel):
    id: UUID
    action: str
    due_at: datetime
    timezone: str | None = None


class LightSummary(BaseModel):
    id: UUID
    classification: LightClassification
    lux: float | None = None
    reliability: MeasurementReliability
    source: MeasurementSource
    measured_at: datetime


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
    next_reminder: ReminderSummary | None = None
    light_summary: LightSummary | None = None
    created_at: datetime


class GardenDeleteResponse(BaseModel):
    status: str
