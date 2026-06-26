"""Shared provider-owned schema shape fragments.

Provider adapters need access to a small set of shape fragments
(``covered_aspects``, ``missing_aspects``, classifier intent/topic enums)
that were previously imported from ``app.assistant.care_contracts``.
This module mirrors the public string values from the assistant
``RequiredAspect`` and ``CareIntent``/``CareTopic`` enums without creating
an import dependency on the assistant slice.
"""

from __future__ import annotations

from enum import Enum


class ProviderCareIntent(str, Enum):
    """Provider-side mirror of the assistant care intent vocabulary."""

    plant_care_question = "plant_care_question"
    plant_identification_question = "plant_identification_question"
    garden_action = "garden_action"
    reminder_request = "reminder_request"
    light_measurement_question = "light_measurement_question"
    out_of_domain = "out_of_domain"
    unsafe_or_injection = "unsafe_or_injection"


PROVIDER_REQUIRED_ASPECT_VALUES: list[str] = [
    "watering_frequency_or_trigger",
    "watering_amount",
    "light_exposure",
    "soil_drainage",
    "pot_drainage",
    "pot_size_guidance",
    "nutrition_feeding_schedule",
    "nutrition_deficiency_signs",
    "nutrition_fertilizer_type",
    "diagnosis_leaf_color_change_causes",
    "diagnosis_leaf_browning_causes",
    "diagnosis_triage_steps",
    "pest_identification",
    "pest_treatment_action",
    "pest_isolation_steps",
    "pest_prevention_steps",
    "disease_identification",
    "disease_treatment_action",
    "disease_prevention_steps",
    "disease_spread_risk",
    "repotting_timing",
    "repotting_post_care",
    "pruning_timing",
    "propagation_rooting_conditions",
    "climate_temperature_range",
    "climate_hardiness",
    "humidity_preference",
    "growth_development_milestones",
    "flowering_fruiting_care",
    "seasonality_dormancy_care",
    "toxicity_pet_safety",
    "toxicity_human_edibility",
    "toxicity_child_safety",
    "toxicity_skin_irritation_risk",
    "toxicity_ingestion_symptoms",
    "toxicity_handling_precautions",
    "safety_chemical_treatment_precautions",
    "safety_disposal_precautions",
    "safety_cross_contamination_prevention",
    "safety_when_to_contact_vet_or_poison_control",
    "taxonomy_native_range",
    "taxonomy_classification",
    "ecology_pollinator_support",
    "ecology_ecosystem_role",
    "general_care_summary",
]


def covered_aspects_array_schema() -> dict:
    """Schema fragment for ``covered_aspects``/``missing_aspects`` arrays."""

    return {
        "type": "array",
        "items": {"type": "string", "enum": list(PROVIDER_REQUIRED_ASPECT_VALUES)},
    }


__all__ = [
    "ProviderCareIntent",
    "PROVIDER_REQUIRED_ASPECT_VALUES",
    "covered_aspects_array_schema",
]
