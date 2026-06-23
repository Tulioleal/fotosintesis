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
    soil_substrate = "soil_substrate"
    pot_container = "pot_container"
    nutrition = "nutrition"
    diagnosis = "diagnosis"
    pests = "pests"
    disease = "disease"
    repotting = "repotting"
    pruning = "pruning"
    propagation = "propagation"
    climate = "climate"
    humidity = "humidity"
    growth_development = "growth_development"
    flowering_fruiting = "flowering_fruiting"
    seasonality_dormancy = "seasonality_dormancy"
    toxicity_safety = "toxicity_safety"
    taxonomy = "taxonomy"
    ecology = "ecology"
    general_care = "general_care"
    unknown = "unknown"


class RequiredAspect(str, Enum):
    # watering
    watering_frequency_or_trigger = "watering_frequency_or_trigger"
    watering_amount = "watering_amount"
    # light
    light_exposure = "light_exposure"
    # soil_substrate
    soil_drainage = "soil_drainage"
    # pot_container
    pot_drainage = "pot_drainage"
    pot_size_guidance = "pot_size_guidance"
    # nutrition
    nutrition_feeding_schedule = "nutrition_feeding_schedule"
    nutrition_deficiency_signs = "nutrition_deficiency_signs"
    nutrition_fertilizer_type = "nutrition_fertilizer_type"
    # diagnosis
    diagnosis_leaf_color_change_causes = "diagnosis_leaf_color_change_causes"
    diagnosis_leaf_browning_causes = "diagnosis_leaf_browning_causes"
    diagnosis_triage_steps = "diagnosis_triage_steps"
    # pests
    pest_identification = "pest_identification"
    pest_treatment_action = "pest_treatment_action"
    pest_isolation_steps = "pest_isolation_steps"
    pest_prevention_steps = "pest_prevention_steps"
    # disease
    disease_identification = "disease_identification"
    disease_treatment_action = "disease_treatment_action"
    disease_prevention_steps = "disease_prevention_steps"
    disease_spread_risk = "disease_spread_risk"
    # repotting
    repotting_timing = "repotting_timing"
    repotting_post_care = "repotting_post_care"
    # pruning
    pruning_timing = "pruning_timing"
    # propagation
    propagation_rooting_conditions = "propagation_rooting_conditions"
    # climate
    climate_temperature_range = "climate_temperature_range"
    climate_hardiness = "climate_hardiness"
    # humidity
    humidity_preference = "humidity_preference"
    # growth_development
    growth_development_milestones = "growth_development_milestones"
    # flowering_fruiting
    flowering_fruiting_care = "flowering_fruiting_care"
    # seasonality_dormancy
    seasonality_dormancy_care = "seasonality_dormancy_care"
    # toxicity_safety
    toxicity_pet_safety = "toxicity_pet_safety"
    toxicity_human_edibility = "toxicity_human_edibility"
    toxicity_child_safety = "toxicity_child_safety"
    toxicity_skin_irritation_risk = "toxicity_skin_irritation_risk"
    toxicity_ingestion_symptoms = "toxicity_ingestion_symptoms"
    toxicity_handling_precautions = "toxicity_handling_precautions"
    safety_chemical_treatment_precautions = "safety_chemical_treatment_precautions"
    safety_disposal_precautions = "safety_disposal_precautions"
    safety_cross_contamination_prevention = "safety_cross_contamination_prevention"
    safety_when_to_contact_vet_or_poison_control = "safety_when_to_contact_vet_or_poison_control"
    # taxonomy
    taxonomy_native_range = "taxonomy_native_range"
    taxonomy_classification = "taxonomy_classification"
    # ecology
    ecology_pollinator_support = "ecology_pollinator_support"
    ecology_ecosystem_role = "ecology_ecosystem_role"
    # general_care
    general_care_summary = "general_care_summary"


SAFETY_SENSITIVE_ASPECTS = {
    RequiredAspect.toxicity_pet_safety,
    RequiredAspect.toxicity_human_edibility,
    RequiredAspect.toxicity_child_safety,
    RequiredAspect.toxicity_skin_irritation_risk,
    RequiredAspect.toxicity_ingestion_symptoms,
    RequiredAspect.toxicity_handling_precautions,
    RequiredAspect.safety_chemical_treatment_precautions,
    RequiredAspect.safety_disposal_precautions,
    RequiredAspect.safety_cross_contamination_prevention,
    RequiredAspect.safety_when_to_contact_vet_or_poison_control,
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
    llm_general_guidance_used: bool = False
