"""Deterministic evidence fingerprints and aspect-to-section mapping.

A profile section's fingerprint is derived only from the accepted evidence
identifiers (canonical source URL + source version) that support its aspects,
so it never depends on retrieval order or model response formatting. When the
same accepted evidence set is used to regenerate a section, the fingerprint is
identical, which lets refresh jobs collapse duplicate work and lets callers
detect staleness.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping

# Canonical aspects supported by the enrichment policy v1 registry. A section
# maps to the aspects whose accepted evidence informs its content.
SECTION_ASPECTS: Mapping[str, tuple[str, ...]] = {
    "description": ("general_care_summary",),
    "characteristics": (),
    "conditions": (
        "light_exposure",
        "soil_drainage",
        "climate_temperature_range",
        "humidity_preference",
    ),
    "care": (
        "general_care_summary",
        "light_exposure",
        "soil_drainage",
        "climate_temperature_range",
        "humidity_preference",
        "watering_frequency_or_trigger",
        "watering_amount",
        "nutrition_feeding_schedule",
        "nutrition_fertilizer_type",
    ),
    "pests": (
        "pest_identification",
        "pest_prevention_steps",
    ),
    "diseases": (
        "disease_identification",
        "disease_prevention_steps",
    ),
    "recommendations": (
        "watering_frequency_or_trigger",
        "watering_amount",
        "nutrition_feeding_schedule",
        "nutrition_fertilizer_type",
        "toxicity_pet_safety",
        "toxicity_human_edibility",
        "toxicity_child_safety",
        "toxicity_handling_precautions",
    ),
}

# Reverse mapping: aspect -> sections that depend on it.
_ASPECT_SECTIONS: dict[str, tuple[str, ...]] = {}
for _section, _aspects in SECTION_ASPECTS.items():
    for _aspect in _aspects:
        _ASPECT_SECTIONS.setdefault(_aspect, []).append(_section)
for _aspect in list(_ASPECT_SECTIONS):
    _ASPECT_SECTIONS[_aspect] = tuple(_ASPECT_SECTIONS[_aspect])


def sections_for_aspects(aspects: Iterable[str]) -> frozenset[str]:
    """Return the profile sections affected by the given canonical aspects."""
    affected: set[str] = set()
    for aspect in aspects:
        affected.update(_ASPECT_SECTIONS.get(aspect, ()))
    return frozenset(affected)


def compute_evidence_fingerprint(
    *,
    evidence: Iterable[Mapping[str, object]],
    generation_policy_version: int,
) -> str:
    """Compute a deterministic fingerprint from accepted evidence.

    ``evidence`` items must expose ``source_url`` and ``source_version`` keys.
    The fingerprint is stable across retrieval order and formatting because it
    is derived from a sorted, compact JSON encoding of identifiers plus the
    generation policy version.
    """
    identifiers = sorted(
        {
            (
                str(item["source_url"]),
                str(item.get("source_version") or ""),
            )
            for item in evidence
        }
    )
    raw = json.dumps(
        {
            "gv": generation_policy_version,
            "evidence": identifiers,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(raw.encode()).hexdigest()


def fingerprint_for_section(
    *,
    section: str,
    evidence: Iterable[Mapping[str, object]],
    generation_policy_version: int,
) -> str:
    """Compute the fingerprint for a single section from its mapped aspects.

    Evidence is filtered to the section's canonical aspect set before the
    fingerprint is derived, so a section only changes when evidence relevant
    to its own aspects changes.
    """
    aspects = set(SECTION_ASPECTS.get(section, ()))
    relevant = [
        item for item in evidence if str(item.get("aspect") or "") in aspects
    ]
    return compute_evidence_fingerprint(
        evidence=relevant,
        generation_policy_version=generation_policy_version,
    )


__all__ = [
    "SECTION_ASPECTS",
    "compute_evidence_fingerprint",
    "fingerprint_for_section",
    "sections_for_aspects",
]
