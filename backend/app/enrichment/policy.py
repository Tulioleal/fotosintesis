from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from types import MappingProxyType

from app.assistant.aspects.registry import REQUIRED_ASPECT_METADATA
from app.assistant.care_contracts import RequiredAspect


RELEASED_POLICY_FINGERPRINTS: dict[int, str] = {
    1: "1afb9b1b8e1ccde8f228d28da93b39f83f207e4782898584785475f19f86f1ae",
}


@dataclass(frozen=True)
class EnrichmentPolicy:
    version: int
    search_groups: tuple[tuple[RequiredAspect, ...], ...]
    max_aspects_per_search_group: int
    max_searches: int
    max_durable_attempts: int
    acceptance_semantics: str

    def __post_init__(self) -> None:
        if self.version < 1:
            raise ValueError("policy version must be positive")
        if not self.search_groups or len(self.search_groups) > self.max_searches:
            raise ValueError("search groups exceed the policy search bound")
        if any(
            not group or len(group) > self.max_aspects_per_search_group
            for group in self.search_groups
        ):
            raise ValueError("search group exceeds the policy aspect bound")
        flattened = tuple(aspect for group in self.search_groups for aspect in group)
        if len(flattened) != len(set(flattened)):
            raise ValueError("required aspects must occur in exactly one search group")
        if any(aspect not in REQUIRED_ASPECT_METADATA for aspect in flattened):
            raise ValueError("required aspects must belong to the canonical registry")
        if self.max_durable_attempts < 1:
            raise ValueError("max_durable_attempts must be positive")
        if not self.acceptance_semantics.strip():
            raise ValueError("acceptance_semantics must be explicit")

    @property
    def required_aspects(self) -> frozenset[RequiredAspect]:
        return frozenset(aspect for group in self.search_groups for aspect in group)

    @property
    def safety_sensitive_aspects(self) -> frozenset[RequiredAspect]:
        return frozenset(
            aspect
            for aspect in self.required_aspects
            if REQUIRED_ASPECT_METADATA[aspect].safety_sensitive
        )

    @property
    def semantics_fingerprint(self) -> str:
        raw = json.dumps(
            {
                "required_aspects": sorted(aspect.value for aspect in self.required_aspects),
                "search_groups": [
                    [aspect.value for aspect in group] for group in self.search_groups
                ],
                "max_aspects_per_search_group": self.max_aspects_per_search_group,
                "max_searches": self.max_searches,
                "max_durable_attempts": self.max_durable_attempts,
                "acceptance_semantics": self.acceptance_semantics,
                "safety_sensitive_aspects": sorted(
                    aspect.value for aspect in self.safety_sensitive_aspects
                ),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(raw.encode()).hexdigest()


def policy_change_requires_version_bump(
    previous: EnrichmentPolicy, current: EnrichmentPolicy
) -> bool:
    """Return whether changed semantics improperly retain the same version."""

    return (
        previous.semantics_fingerprint != current.semantics_fingerprint
        and previous.version == current.version
    )


ENRICHMENT_POLICY_V1 = EnrichmentPolicy(
    version=1,
    search_groups=(
        (RequiredAspect.general_care_summary,),
        (
            RequiredAspect.light_exposure,
            RequiredAspect.soil_drainage,
            RequiredAspect.climate_temperature_range,
            RequiredAspect.humidity_preference,
        ),
        (
            RequiredAspect.watering_frequency_or_trigger,
            RequiredAspect.watering_amount,
            RequiredAspect.nutrition_feeding_schedule,
            RequiredAspect.nutrition_fertilizer_type,
        ),
        (
            RequiredAspect.pest_identification,
            RequiredAspect.pest_prevention_steps,
            RequiredAspect.disease_identification,
            RequiredAspect.disease_prevention_steps,
        ),
        (
            RequiredAspect.toxicity_pet_safety,
            RequiredAspect.toxicity_human_edibility,
            RequiredAspect.toxicity_child_safety,
            RequiredAspect.toxicity_handling_precautions,
        ),
    ),
    max_aspects_per_search_group=4,
    max_searches=5,
    max_durable_attempts=3,
    acceptance_semantics="registry_answerability_v1",
)

ENRICHMENT_POLICIES = MappingProxyType({
    1: ENRICHMENT_POLICY_V1,
})

CURRENT_ENRICHMENT_POLICY_VERSION = max(ENRICHMENT_POLICIES)


def get_enrichment_policy(version: int) -> EnrichmentPolicy:
    try:
        return ENRICHMENT_POLICIES[version]
    except KeyError as exc:
        raise ValueError(
            f"unsupported enrichment policy version: {version}"
        ) from exc


def get_current_enrichment_policy() -> EnrichmentPolicy:
    return get_enrichment_policy(
        CURRENT_ENRICHMENT_POLICY_VERSION
    )


__all__ = [
    "CURRENT_ENRICHMENT_POLICY_VERSION",
    "ENRICHMENT_POLICIES",
    "ENRICHMENT_POLICY_V1",
    "EnrichmentPolicy",
    "get_current_enrichment_policy",
    "get_enrichment_policy",
    "policy_change_requires_version_bump",
]
