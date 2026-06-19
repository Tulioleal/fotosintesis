"""Centralized metadata registry for RequiredAspect semantics.

This module defines structured metadata for each RequiredAspect, including
domain, label, query label, search terms, optional coverage guidance,
safety sensitivity, and optional diagnostic label.

The registry is the single source of truth for aspect semantics consumed by
the answerability judge, web fallback query construction, safety threshold
selection, and diagnostics. Deterministic keyword matching MUST NOT decide
whether evidence covers an aspect; that is the answerability judge's role.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.assistant.care_contracts import RequiredAspect, SAFETY_SENSITIVE_ASPECTS


@dataclass(frozen=True)
class RequiredAspectMetadata:
    """Structured metadata for a single RequiredAspect."""

    domain: str
    label: str
    query_label: str
    search_terms: tuple[str, ...]
    coverage_guidance: str | None = None
    safety_sensitive: bool = False
    diagnostic_label: str | None = None


REQUIRED_ASPECT_METADATA: dict[RequiredAspect, RequiredAspectMetadata] = {
    # --- watering ---
    RequiredAspect.watering_frequency_or_trigger: RequiredAspectMetadata(
        domain="watering",
        label="watering frequency or trigger",
        query_label="watering frequency or soil dryness trigger",
        search_terms=(
            "watering frequency",
            "watering trigger",
            "soil dry",
            "dry between watering",
        ),
        coverage_guidance=(
            "This aspect is covered by either a fixed watering interval or a "
            "condition-based trigger. For questions like 'how often should I "
            "water?', evidence such as 'water when the soil is dry', 'water "
            "when the substrate dries', 'let the top layer dry before watering', "
            "or equivalent phrasing directly answers the requested aspect, even "
            "if no calendar interval is given. Do not mark it insufficient "
            "merely because the evidence corrects the premise of watering by "
            "fixed time."
        ),
    ),
    RequiredAspect.watering_amount: RequiredAspectMetadata(
        domain="watering",
        label="watering amount",
        query_label="watering amount and thoroughness",
        search_terms=("watering amount", "how much water", "thorough watering"),
    ),
    # --- light ---
    RequiredAspect.light_exposure: RequiredAspectMetadata(
        domain="light",
        label="light exposure",
        query_label="light exposure requirements",
        search_terms=("light exposure", "light requirements", "sunlight needs"),
    ),
    # --- soil_substrate ---
    RequiredAspect.soil_drainage: RequiredAspectMetadata(
        domain="soil_substrate",
        label="soil drainage",
        query_label="soil drainage requirements",
        search_terms=("soil drainage", "well-draining soil", "substrate mix"),
    ),
    # --- pot_container ---
    RequiredAspect.pot_drainage: RequiredAspectMetadata(
        domain="pot_container",
        label="pot drainage",
        query_label="pot drainage holes",
        search_terms=("pot drainage", "drainage holes", "container drainage"),
    ),
    RequiredAspect.pot_size_guidance: RequiredAspectMetadata(
        domain="pot_container",
        label="pot size guidance",
        query_label="pot size and repotting guidance",
        search_terms=("pot size", "repotting size", "container size"),
    ),
    # --- nutrition ---
    RequiredAspect.nutrition_feeding_schedule: RequiredAspectMetadata(
        domain="nutrition",
        label="feeding schedule",
        query_label="feeding and fertilization schedule",
        search_terms=(
            "fertilization schedule",
            "feeding frequency",
            "fertilizer routine",
        ),
    ),
    RequiredAspect.nutrition_deficiency_signs: RequiredAspectMetadata(
        domain="nutrition",
        label="deficiency signs",
        query_label="nutrient deficiency signs",
        search_terms=(
            "nutrient deficiency signs",
            "yellow leaves nutrient",
            "chlorosis",
        ),
    ),
    RequiredAspect.nutrition_fertilizer_type: RequiredAspectMetadata(
        domain="nutrition",
        label="fertilizer type",
        query_label="fertilizer type and formulation",
        search_terms=("fertilizer type", "fertilizer formulation", "liquid fertilizer"),
    ),
    # --- diagnosis ---
    RequiredAspect.diagnosis_leaf_color_change_causes: RequiredAspectMetadata(
        domain="diagnosis",
        label="causes of leaf color changes",
        query_label="leaf color change causes",
        search_terms=(
            "leaf color changes",
            "yellow leaves causes",
            "chlorosis causes",
            "houseplant leaf discoloration",
        ),
        coverage_guidance=(
            "This aspect is covered when evidence explains possible causes of "
            "leaf color changes such as yellowing, chlorosis, or discoloration. "
            "Present causes as hypotheses or possibilities unless source-supported "
            "evidence directly identifies the cause for the specific plant and "
            "symptom context."
        ),
    ),
    RequiredAspect.diagnosis_leaf_browning_causes: RequiredAspectMetadata(
        domain="diagnosis",
        label="causes of leaf browning",
        query_label="leaf browning causes",
        search_terms=(
            "leaf browning causes",
            "brown leaf tips",
            "leaf scorch",
            "houseplant brown leaves",
        ),
        coverage_guidance=(
            "This aspect is covered when evidence explains possible causes of "
            "leaf browning, scorch, or burn marks. Present causes as hypotheses "
            "or possibilities unless source-supported evidence directly identifies "
            "the cause."
        ),
    ),
    RequiredAspect.diagnosis_triage_steps: RequiredAspectMetadata(
        domain="diagnosis",
        label="diagnostic triage steps",
        query_label="diagnostic triage steps",
        search_terms=(
            "plant diagnosis steps",
            "diagnostic triage",
            "symptom assessment",
        ),
        coverage_guidance=(
            "This aspect is covered when evidence provides diagnostic steps, "
            "triage guidance, or symptom assessment for the described plant "
            "problem. Present causes as hypotheses unless directly supported."
        ),
    ),
    # --- pests ---
    RequiredAspect.pest_identification: RequiredAspectMetadata(
        domain="pests",
        label="pest identification",
        query_label="pest identification",
        search_terms=("pest identification", "insect identification", "houseplant pests"),
    ),
    RequiredAspect.pest_treatment_action: RequiredAspectMetadata(
        domain="pests",
        label="pest treatment action",
        query_label="pest treatment and control",
        search_terms=("pest treatment", "pest control", "insecticide"),
    ),
    RequiredAspect.pest_isolation_steps: RequiredAspectMetadata(
        domain="pests",
        label="pest isolation steps",
        query_label="pest isolation steps",
        search_terms=("isolate plant", "pest isolation", "separate plant"),
    ),
    RequiredAspect.pest_prevention_steps: RequiredAspectMetadata(
        domain="pests",
        label="pest prevention steps",
        query_label="pest prevention steps",
        search_terms=("pest prevention", "prevent pests", "pest control routine"),
    ),
    # --- disease ---
    RequiredAspect.disease_identification: RequiredAspectMetadata(
        domain="disease",
        label="disease identification",
        query_label="disease identification",
        search_terms=("plant disease", "fungal infection", "bacterial disease"),
    ),
    RequiredAspect.disease_treatment_action: RequiredAspectMetadata(
        domain="disease",
        label="disease treatment action",
        query_label="disease treatment and control",
        search_terms=("disease treatment", "fungicide", "plant disease control"),
    ),
    RequiredAspect.disease_prevention_steps: RequiredAspectMetadata(
        domain="disease",
        label="disease prevention steps",
        query_label="disease prevention steps",
        search_terms=("disease prevention", "prevent fungal", "ventilation"),
    ),
    RequiredAspect.disease_spread_risk: RequiredAspectMetadata(
        domain="disease",
        label="disease spread risk",
        query_label="disease spread risk",
        search_terms=("disease spread", "contagious disease", "disease transmission"),
    ),
    # --- repotting ---
    RequiredAspect.repotting_timing: RequiredAspectMetadata(
        domain="repotting",
        label="repotting timing",
        query_label="repotting timing",
        search_terms=("repotting timing", "when to repot", "root bound signs"),
    ),
    RequiredAspect.repotting_post_care: RequiredAspectMetadata(
        domain="repotting",
        label="repotting post care",
        query_label="post-repotting care",
        search_terms=("after repotting", "repotting care", "transplant recovery"),
    ),
    # --- pruning ---
    RequiredAspect.pruning_timing: RequiredAspectMetadata(
        domain="pruning",
        label="pruning timing",
        query_label="pruning timing and technique",
        search_terms=("pruning timing", "when to prune", "pruning technique"),
    ),
    # --- propagation ---
    RequiredAspect.propagation_rooting_conditions: RequiredAspectMetadata(
        domain="propagation",
        label="propagation rooting conditions",
        query_label="propagation rooting conditions",
        search_terms=(
            "propagation conditions",
            "rooting cuttings",
            "plant propagation",
        ),
    ),
    # --- climate ---
    RequiredAspect.climate_temperature_range: RequiredAspectMetadata(
        domain="climate",
        label="temperature range",
        query_label="temperature range and tolerance",
        search_terms=(
            "temperature range",
            "minimum temperature",
            "frost tolerance",
        ),
    ),
    RequiredAspect.climate_hardiness: RequiredAspectMetadata(
        domain="climate",
        label="hardiness zone",
        query_label="hardiness zone and cold tolerance",
        search_terms=("hardiness zone", "cold tolerance", "USDA zone"),
    ),
    # --- humidity ---
    RequiredAspect.humidity_preference: RequiredAspectMetadata(
        domain="humidity",
        label="humidity preference",
        query_label="humidity preference and requirements",
        search_terms=("humidity preference", "humidity requirements", "misting"),
    ),
    # --- growth_development ---
    RequiredAspect.growth_development_milestones: RequiredAspectMetadata(
        domain="growth_development",
        label="growth milestones",
        query_label="growth and development milestones",
        search_terms=("growth milestones", "plant growth stages", "development"),
    ),
    # --- flowering_fruiting ---
    RequiredAspect.flowering_fruiting_care: RequiredAspectMetadata(
        domain="flowering_fruiting",
        label="flowering and fruiting care",
        query_label="flowering and fruiting care",
        search_terms=("flowering care", "bloom care", "fruiting conditions"),
    ),
    # --- seasonality_dormancy ---
    RequiredAspect.seasonality_dormancy_care: RequiredAspectMetadata(
        domain="seasonality_dormancy",
        label="seasonal and dormancy care",
        query_label="seasonal care and dormancy management",
        search_terms=(
            "dormancy care",
            "seasonal care",
            "winter care",
            "summer care",
        ),
    ),
    # --- toxicity_safety ---
    RequiredAspect.toxicity_pet_safety: RequiredAspectMetadata(
        domain="toxicity",
        label="pet toxicity",
        query_label="toxicity to cats and dogs",
        search_terms=(
            "toxic to cats",
            "toxic to dogs",
            "pet toxicity",
            "ASPCA toxic",
        ),
        coverage_guidance=(
            "This is a safety-sensitive aspect. Evidence must directly state "
            "whether the plant is toxic or safe for pets (cats, dogs, etc.). "
            "General toxicity information without pet-specific mention does not "
            "cover this aspect."
        ),
        safety_sensitive=True,
    ),
    RequiredAspect.toxicity_human_edibility: RequiredAspectMetadata(
        domain="toxicity",
        label="human edibility",
        query_label="edibility and human consumption safety",
        search_terms=(
            "edible plant",
            "safe to eat",
            "human consumption",
            "toxic to humans",
        ),
        coverage_guidance=(
            "This is a safety-sensitive aspect. Evidence must directly address "
            "whether the plant is safe for human consumption. General botanical "
            "information without edibility mention does not cover this aspect."
        ),
        safety_sensitive=True,
    ),
    RequiredAspect.toxicity_child_safety: RequiredAspectMetadata(
        domain="toxicity",
        label="child safety",
        query_label="safety around children",
        search_terms=(
            "safe for children",
            "child toxicity",
            "toxic to children",
        ),
        coverage_guidance=(
            "This is a safety-sensitive aspect. Evidence must directly address "
            "whether the plant is safe around children."
        ),
        safety_sensitive=True,
    ),
    RequiredAspect.toxicity_skin_irritation_risk: RequiredAspectMetadata(
        domain="toxicity",
        label="skin irritation risk",
        query_label="skin irritation and contact risk",
        search_terms=(
            "skin irritation",
            "contact dermatitis",
            "skin contact risk",
        ),
        coverage_guidance=(
            "This is a safety-sensitive aspect. Evidence must directly address "
            "skin contact risks or irritation potential."
        ),
        safety_sensitive=True,
    ),
    RequiredAspect.toxicity_ingestion_symptoms: RequiredAspectMetadata(
        domain="toxicity",
        label="ingestion symptoms",
        query_label="ingestion symptoms and effects",
        search_terms=(
            "ingestion symptoms",
            "poisoning symptoms",
            "if eaten symptoms",
        ),
        safety_sensitive=True,
    ),
    RequiredAspect.toxicity_handling_precautions: RequiredAspectMetadata(
        domain="toxicity",
        label="handling precautions",
        query_label="safe handling precautions",
        search_terms=(
            "handling precautions",
            "safe handling",
            "gloves when handling",
        ),
        safety_sensitive=True,
    ),
    RequiredAspect.safety_chemical_treatment_precautions: RequiredAspectMetadata(
        domain="safety",
        label="chemical treatment precautions",
        query_label="chemical treatment safety precautions",
        search_terms=(
            "chemical treatment safety",
            "pesticide precautions",
            "chemical handling safety",
        ),
        safety_sensitive=True,
    ),
    RequiredAspect.safety_disposal_precautions: RequiredAspectMetadata(
        domain="safety",
        label="disposal precautions",
        query_label="safe disposal precautions",
        search_terms=(
            "disposal precautions",
            "safe disposal",
            "plant disposal safety",
        ),
        safety_sensitive=True,
    ),
    RequiredAspect.safety_cross_contamination_prevention: RequiredAspectMetadata(
        domain="safety",
        label="cross-contamination prevention",
        query_label="cross-contamination prevention",
        search_terms=(
            "cross contamination prevention",
            "disease spread prevention",
            "sanitation",
        ),
        safety_sensitive=True,
    ),
    RequiredAspect.safety_when_to_contact_vet_or_poison_control: RequiredAspectMetadata(
        domain="safety",
        label="when to contact vet or poison control",
        query_label="when to contact vet or poison control",
        search_terms=(
            "vet emergency",
            "poison control",
            "veterinary emergency",
        ),
        safety_sensitive=True,
    ),
    # --- taxonomy ---
    RequiredAspect.taxonomy_native_range: RequiredAspectMetadata(
        domain="taxonomy",
        label="native range",
        query_label="native range and distribution",
        search_terms=("native range", "natural distribution", "origin habitat"),
    ),
    RequiredAspect.taxonomy_classification: RequiredAspectMetadata(
        domain="taxonomy",
        label="taxonomic classification",
        query_label="taxonomic classification",
        search_terms=("species classification", "genus family", "taxonomy"),
    ),
    # --- ecology ---
    RequiredAspect.ecology_pollinator_support: RequiredAspectMetadata(
        domain="ecology",
        label="pollinator support",
        query_label="pollinator support value",
        search_terms=("pollinator support", "bee friendly", "butterfly attract"),
    ),
    RequiredAspect.ecology_ecosystem_role: RequiredAspectMetadata(
        domain="ecology",
        label="ecosystem role",
        query_label="ecosystem role and habitat value",
        search_terms=("ecosystem role", "habitat value", "ecological function"),
    ),
    # --- general_care ---
    RequiredAspect.general_care_summary: RequiredAspectMetadata(
        domain="general_care",
        label="general care summary",
        query_label="general care summary",
        search_terms=("general care", "care guide", "cultivation"),
    ),
}


def metadata_for_aspect(aspect: RequiredAspect | str) -> RequiredAspectMetadata | None:
    """Look up metadata by RequiredAspect member or canonical string value."""
    if isinstance(aspect, RequiredAspect):
        return REQUIRED_ASPECT_METADATA.get(aspect)
    try:
        member = RequiredAspect(aspect)
    except ValueError:
        return None
    return REQUIRED_ASPECT_METADATA.get(member)


def aspect_query_terms(aspects: list[str]) -> list[str]:
    """Return human-readable query terms for the given aspect strings.

    Uses metadata query_label and search_terms when available, falling back
    to underscore-replaced enum values for unknown aspects.
    """
    seen: set[str] = set()
    result: list[str] = []
    for aspect_str in aspects:
        md = metadata_for_aspect(aspect_str)
        if md is not None:
            if md.query_label not in seen:
                seen.add(md.query_label)
                result.append(md.query_label)
            for term in md.search_terms:
                if term not in seen:
                    seen.add(term)
                    result.append(term)
        else:
            fallback = aspect_str.replace("_", " ")
            if fallback not in seen:
                seen.add(fallback)
                result.append(fallback)
    return result


def aspect_validation_guidance(required_aspects: list[str]) -> dict[str, str]:
    """Return coverage_guidance for requested aspects that define it.

    Only aspects with non-None coverage_guidance in metadata are included.
    """
    result: dict[str, str] = {}
    for aspect_str in required_aspects:
        md = metadata_for_aspect(aspect_str)
        if md is not None and md.coverage_guidance is not None:
            result[aspect_str] = md.coverage_guidance
    return result


def is_safety_sensitive_aspect(aspect: RequiredAspect | str) -> bool:
    """Check whether an aspect is safety-sensitive using metadata.

    Falls back to the existing SAFETY_SENSITIVE_ASPECTS set when the
    aspect cannot be resolved to metadata.
    """
    md = metadata_for_aspect(aspect)
    if md is not None:
        return md.safety_sensitive
    # Fallback: resolve to enum member and check existing constant
    if isinstance(aspect, str):
        try:
            member = RequiredAspect(aspect)
        except ValueError:
            return False
        return member in SAFETY_SENSITIVE_ASPECTS
    return aspect in SAFETY_SENSITIVE_ASPECTS
