from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class IdentificationStatus(str, Enum):
    needs_confirmation = "needs_confirmation"
    retry_needed = "retry_needed"
    no_reliable_candidate = "no_reliable_candidate"


class ValidationStatus(str, Enum):
    validated = "validated"
    no_gbif_match = "no_gbif_match"


class TaxonomyCandidate(BaseModel):
    id: UUID
    common_name: str | None = None
    suggested_scientific_name: str
    confidence_label: str
    visible_traits: list[str] = Field(default_factory=list)
    possible_match_copy: str
    gbif_key: int | None = None
    gbif_accepted_key: int | None = None
    accepted_scientific_name: str | None = None
    binomial_name: str | None = None
    taxonomic_status: str | None = None
    synonyms: list[str] = Field(default_factory=list)
    genus: str | None = None
    family: str | None = None
    species: str | None = None
    validation_status: ValidationStatus
    confirmed_at: datetime | None = None


class IdentificationResponse(BaseModel):
    id: UUID
    status: IdentificationStatus
    sad_path: str | None = None
    message: str
    image: dict[str, object]
    candidates: list[TaxonomyCandidate] = Field(default_factory=list)


class ConfirmationResponse(BaseModel):
    status: str
    candidate: TaxonomyCandidate
