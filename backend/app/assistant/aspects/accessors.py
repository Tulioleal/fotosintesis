"""Accessor helpers for the aspect metadata registry."""

from __future__ import annotations

from app.assistant.aspects.registry import REQUIRED_ASPECT_METADATA, RequiredAspectMetadata
from app.assistant.care_contracts import RequiredAspect, SAFETY_SENSITIVE_ASPECTS


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
    """Return query terms for the requested aspects.

    Terms are deduplicated while preserving first appearance. Unknown
    aspects fall back to an underscore-replaced label to preserve the
    top-level shim's historical behavior.
    """
    seen: set[str] = set()
    result: list[str] = []
    for aspect in aspects:
        metadata = metadata_for_aspect(aspect)
        if metadata is None:
            fallback = aspect.replace("_", " ")
            if fallback and fallback not in seen:
                seen.add(fallback)
                result.append(fallback)
            continue
        for term in (metadata.query_label, *metadata.search_terms):
            if term and term not in seen:
                seen.add(term)
                result.append(term)
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


__all__ = [
    "aspect_query_terms",
    "aspect_validation_guidance",
    "is_safety_sensitive_aspect",
    "metadata_for_aspect",
]
