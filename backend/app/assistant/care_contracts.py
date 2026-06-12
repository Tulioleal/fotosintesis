from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CareIntent(str, Enum):
    plant_care_question = "plant_care_question"
    plant_identification_question = "plant_identification_question"
    garden_action = "garden_action"
    reminder_request = "reminder_request"
    light_measurement_question = "light_measurement_question"
    out_of_domain = "out_of_domain"
    unsafe_or_injection = "unsafe_or_injection"


class CareTopic(str, Enum):
    watering = "watering"
    light = "light"
    soil = "soil"
    fertilizer = "fertilizer"
    pruning = "pruning"
    pests = "pests"
    toxicity = "toxicity"
    temperature = "temperature"
    humidity = "humidity"
    repotting = "repotting"
    general_care = "general_care"
    unknown = "unknown"


class RequiredAspect(str, Enum):
    watering_frequency_or_trigger = "watering_frequency_or_trigger"
    watering_amount = "watering_amount"
    light_exposure = "light_exposure"
    soil_drainage = "soil_drainage"
    fertilizer_frequency = "fertilizer_frequency"
    pruning_timing = "pruning_timing"
    pest_identification = "pest_identification"
    treatment_action = "treatment_action"
    repotting_timing = "repotting_timing"
    temperature_range = "temperature_range"
    humidity_preference = "humidity_preference"
    native_range = "native_range"
    pet_toxicity = "pet_toxicity"
    human_edibility = "human_edibility"
    general_care_summary = "general_care_summary"


SAFETY_SENSITIVE_ASPECTS = {
    RequiredAspect.pet_toxicity,
    RequiredAspect.human_edibility,
}


class CareClassification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    language: str = "es"
    answer_language: str = "es"
    intent: CareIntent
    topic: CareTopic = CareTopic.unknown
    required_aspects: list[RequiredAspect] = Field(default_factory=list)
    plant_reference: str | None = None
    confidence: float = Field(ge=0, le=1)
    needs_retrieval: bool = False
    source: Literal["llm", "deterministic"] = "llm"

    @field_validator("language", "answer_language")
    @classmethod
    def _normalize_language(cls, value: str) -> str:
        normalized = value.strip().lower()
        return normalized or "es"


class EvidenceValidationResult(BaseModel):
    answerable: bool = False
    covered_aspects: list[RequiredAspect] = Field(default_factory=list)
    missing_aspects: list[RequiredAspect] = Field(default_factory=list)
    unsupported_claims_risk: bool = False
    reason: str = "Evidence did not validate against requested aspects."
    confidence: float = Field(default=0.0, ge=0, le=1)

    @field_validator("covered_aspects")
    @classmethod
    def _dedupe_covered(cls, value: list[RequiredAspect]) -> list[RequiredAspect]:
        return list(dict.fromkeys(value))

    @field_validator("missing_aspects")
    @classmethod
    def _dedupe_missing(cls, value: list[RequiredAspect]) -> list[RequiredAspect]:
        return list(dict.fromkeys(value))


class CareDiagnostics(BaseModel):
    intent: CareIntent | None = None
    topic: CareTopic | None = None
    required_aspects: list[RequiredAspect] = Field(default_factory=list)
    covered_aspects: list[RequiredAspect] = Field(default_factory=list)
    missing_aspects: list[RequiredAspect] = Field(default_factory=list)
    evidence_path: list[str] = Field(default_factory=list)
    answer_language: str | None = None
