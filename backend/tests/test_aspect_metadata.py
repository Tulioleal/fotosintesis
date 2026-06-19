"""Tests for the aspect metadata registry."""

from __future__ import annotations

import pytest

from app.assistant.aspect_metadata import (
    REQUIRED_ASPECT_METADATA,
    aspect_query_terms,
    aspect_validation_guidance,
    is_safety_sensitive_aspect,
    metadata_for_aspect,
)
from app.assistant.care_contracts import RequiredAspect


class TestMetadataForAspect:
    """Tests for metadata_for_aspect lookup."""

    def test_lookup_by_enum_member(self) -> None:
        md = metadata_for_aspect(RequiredAspect.watering_frequency_or_trigger)
        assert md is not None
        assert md.domain == "watering"
        assert md.label == "watering frequency or trigger"
        assert md.query_label == "watering frequency or soil dryness trigger"
        assert len(md.search_terms) > 0

    def test_lookup_by_canonical_string(self) -> None:
        md = metadata_for_aspect("watering_frequency_or_trigger")
        assert md is not None
        assert md.domain == "watering"
        assert md.label == "watering frequency or trigger"

    def test_lookup_unguided_aspect(self) -> None:
        md = metadata_for_aspect(RequiredAspect.soil_drainage)
        assert md is not None
        assert md.domain == "soil_substrate"
        assert md.coverage_guidance is None

    def test_lookup_safety_sensitive_aspect(self) -> None:
        md = metadata_for_aspect(RequiredAspect.toxicity_pet_safety)
        assert md is not None
        assert md.safety_sensitive is True

    def test_unknown_string_returns_none(self) -> None:
        md = metadata_for_aspect("unknown_aspect")
        assert md is None

    def test_all_required_aspects_have_metadata(self) -> None:
        for aspect in RequiredAspect:
            md = metadata_for_aspect(aspect)
            assert md is not None, f"Missing metadata for {aspect.value}"
            assert md.domain, f"Empty domain for {aspect.value}"
            assert md.label, f"Empty label for {aspect.value}"
            assert md.query_label, f"Empty query_label for {aspect.value}"
            assert md.search_terms, f"Empty search_terms for {aspect.value}"


class TestAspectQueryTerms:
    """Tests for aspect_query_terms helper."""

    def test_returns_query_label_and_search_terms(self) -> None:
        terms = aspect_query_terms(["watering_frequency_or_trigger"])
        assert "watering frequency or soil dryness trigger" in terms
        assert "watering frequency" in terms
        assert "soil dry" in terms

    def test_deduplicates_across_aspects(self) -> None:
        terms = aspect_query_terms([
            "watering_frequency_or_trigger",
            "watering_amount",
        ])
        assert "water" not in terms[1:] or terms.count("water") <= 1

    def test_unknown_aspect_falls_back_to_underscore_replacement(self) -> None:
        terms = aspect_query_terms(["unknown_foo_bar"])
        assert "unknown foo bar" in terms

    def test_empty_list_returns_empty(self) -> None:
        assert aspect_query_terms([]) == []

    def test_mixed_known_and_unknown(self) -> None:
        terms = aspect_query_terms(["light_exposure", "unknown_aspect"])
        assert any("light" in t for t in terms)
        assert "unknown aspect" in terms


class TestAspectValidationGuidance:
    """Tests for aspect_validation_guidance helper."""

    def test_guided_aspect_returns_guidance(self) -> None:
        guidance = aspect_validation_guidance(["watering_frequency_or_trigger"])
        assert "watering_frequency_or_trigger" in guidance
        assert "condition-based trigger" in guidance["watering_frequency_or_trigger"]

    def test_unguided_aspect_omitted(self) -> None:
        guidance = aspect_validation_guidance(["light_exposure"])
        assert guidance == {}

    def test_unknown_aspect_omitted(self) -> None:
        guidance = aspect_validation_guidance(["unknown_aspect"])
        assert guidance == {}

    def test_mixed_guided_and_unguided(self) -> None:
        guidance = aspect_validation_guidance([
            "watering_frequency_or_trigger",
            "light_exposure",
            "unknown_aspect",
        ])
        assert len(guidance) == 1
        assert "watering_frequency_or_trigger" in guidance

    def test_diagnosis_aspects_have_guidance(self) -> None:
        guidance = aspect_validation_guidance([
            "diagnosis_leaf_color_change_causes",
            "diagnosis_leaf_browning_causes",
            "diagnosis_triage_steps",
        ])
        assert len(guidance) == 3
        for key in guidance:
            assert "hypotheses" in guidance[key] or "covered" in guidance[key]


class TestNoDeterministicKeywordGate:
    """Regression: evidence_keywords was removed from metadata.

    Deterministic keyword matching MUST NOT decide whether evidence covers an
    aspect. The answerability judge is the only component that decides coverage.
    """

    def test_metadata_has_no_evidence_keywords_field(self) -> None:
        md = metadata_for_aspect(RequiredAspect.toxicity_pet_safety)
        assert md is not None
        assert not hasattr(md, "evidence_keywords")

    def test_all_metadata_entries_lack_evidence_keywords(self) -> None:
        for aspect in RequiredAspect:
            md = metadata_for_aspect(aspect)
            assert md is not None
            assert not hasattr(md, "evidence_keywords"), (
                f"evidence_keywords still present on {aspect.value}"
            )


class TestIsSafetySensitiveAspect:
    """Tests for is_safety_sensitive_aspect helper."""

    def test_safety_sensitive_by_enum(self) -> None:
        assert is_safety_sensitive_aspect(RequiredAspect.toxicity_pet_safety) is True
        assert is_safety_sensitive_aspect(RequiredAspect.toxicity_human_edibility) is True
        assert is_safety_sensitive_aspect(RequiredAspect.toxicity_child_safety) is True
        assert is_safety_sensitive_aspect(
            RequiredAspect.safety_when_to_contact_vet_or_poison_control
        ) is True

    def test_safety_sensitive_by_string(self) -> None:
        assert is_safety_sensitive_aspect("toxicity_pet_safety") is True
        assert is_safety_sensitive_aspect("toxicity_human_edibility") is True

    def test_non_safety_aspect(self) -> None:
        assert is_safety_sensitive_aspect(RequiredAspect.light_exposure) is False
        assert is_safety_sensitive_aspect(RequiredAspect.soil_drainage) is False

    def test_non_safety_by_string(self) -> None:
        assert is_safety_sensitive_aspect("light_exposure") is False

    def test_unknown_string_returns_false(self) -> None:
        assert is_safety_sensitive_aspect("unknown_aspect") is False

    def test_all_toxicity_aspects_are_safety_sensitive(self) -> None:
        for aspect in RequiredAspect:
            md = metadata_for_aspect(aspect)
            if md is not None and md.safety_sensitive:
                assert is_safety_sensitive_aspect(aspect) is True, (
                    f"{aspect.value} marked safety_sensitive in metadata "
                    f"but is_safety_sensitive_aspect returned False"
                )

    def test_metadata_safety_matches_existing_constant(self) -> None:
        from app.assistant.care_contracts import SAFETY_SENSITIVE_ASPECTS

        for aspect in SAFETY_SENSITIVE_ASPECTS:
            assert is_safety_sensitive_aspect(aspect) is True, (
                f"{aspect.value} in SAFETY_SENSITIVE_ASPECTS but not "
                f"marked safety-sensitive in metadata"
            )


class TestRegistryCompleteness:
    """Verify registry covers all RequiredAspect members."""

    def test_registry_has_all_aspects(self) -> None:
        for aspect in RequiredAspect:
            assert aspect in REQUIRED_ASPECT_METADATA, (
                f"Missing registry entry for {aspect.value}"
            )

    def test_all_safety_aspects_marked_in_metadata(self) -> None:
        from app.assistant.care_contracts import SAFETY_SENSITIVE_ASPECTS

        for aspect in SAFETY_SENSITIVE_ASPECTS:
            md = REQUIRED_ASPECT_METADATA.get(aspect)
            assert md is not None, f"Missing metadata for safety aspect {aspect.value}"
            assert md.safety_sensitive is True, (
                f"Safety aspect {aspect.value} not marked safety_sensitive in metadata"
            )
