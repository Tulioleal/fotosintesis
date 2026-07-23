from dataclasses import replace
from uuid import UUID

import pytest

from app.assistant.aspects.registry import REQUIRED_ASPECT_METADATA
from app.assistant.care_contracts import RequiredAspect
from app.enrichment import (
    ENRICHMENT_POLICY_V1,
    CanonicalSpeciesIdentity,
    EnrichmentWorkflowAspects,
    build_active_work_key,
    build_run_idempotency_key,
    policy_change_requires_version_bump,
)
from app.jobs.schemas import EnrichmentJobResult, EnrichmentLimitation


def _identity(*, key: int | None = 2878688, name: str | None = "Monstera deliciosa"):
    return CanonicalSpeciesIdentity(
        accepted_gbif_key=key,
        normalized_binomial=name,
        taxonomy_validated=True,
    )


def test_canonical_identity_includes_both_validated_taxonomy_values() -> None:
    identity = _identity(name="  MONSTERA   Deliciosa ")

    assert identity.normalized_binomial == "Monstera deliciosa"
    assert identity.key == "gbif:2878688|binomial:Monstera deliciosa"


def test_canonical_identity_uses_validated_binomial_fallback() -> None:
    assert _identity(key=None).key == "binomial:Monstera deliciosa"


def test_canonical_identity_changes_with_either_composite_value() -> None:
    original = _identity()

    assert _identity(key=2878689).key != original.key
    assert _identity(name="Monstera adansonii").key != original.key


@pytest.mark.parametrize(
    ("key", "name", "validated"),
    [
        (None, "Swiss cheese plant", True),
        (None, "Monstera deliciosa", False),
        (None, None, True),
    ],
)
def test_canonical_identity_rejects_display_or_unvalidated_names(
    key: int | None, name: str | None, validated: bool
) -> None:
    with pytest.raises(ValueError):
        CanonicalSpeciesIdentity(
            accepted_gbif_key=key,
            normalized_binomial=name,
            taxonomy_validated=validated,
        )


def test_policy_v1_has_exact_required_aspects_and_registry_safety() -> None:
    expected = {
        RequiredAspect.general_care_summary,
        RequiredAspect.light_exposure,
        RequiredAspect.soil_drainage,
        RequiredAspect.climate_temperature_range,
        RequiredAspect.humidity_preference,
        RequiredAspect.watering_frequency_or_trigger,
        RequiredAspect.watering_amount,
        RequiredAspect.nutrition_feeding_schedule,
        RequiredAspect.nutrition_fertilizer_type,
        RequiredAspect.pest_identification,
        RequiredAspect.pest_prevention_steps,
        RequiredAspect.disease_identification,
        RequiredAspect.disease_prevention_steps,
        RequiredAspect.toxicity_pet_safety,
        RequiredAspect.toxicity_human_edibility,
        RequiredAspect.toxicity_child_safety,
        RequiredAspect.toxicity_handling_precautions,
    }

    assert ENRICHMENT_POLICY_V1.required_aspects == expected
    assert len(ENRICHMENT_POLICY_V1.required_aspects) == 17
    assert ENRICHMENT_POLICY_V1.required_aspects <= REQUIRED_ASPECT_METADATA.keys()
    assert ENRICHMENT_POLICY_V1.safety_sensitive_aspects == {
        aspect
        for aspect in expected
        if REQUIRED_ASPECT_METADATA[aspect].safety_sensitive
    }


def test_policy_v1_obeys_search_and_attempt_bounds() -> None:
    policy = ENRICHMENT_POLICY_V1

    assert policy.max_aspects_per_search_group == 4
    assert all(len(group) <= 4 for group in policy.search_groups)
    assert policy.max_searches == 5
    assert len(policy.search_groups) <= 5
    assert policy.max_durable_attempts == 3

    group_by_aspect = {
        aspect: group_index
        for group_index, group in enumerate(policy.search_groups)
        for aspect in group
    }
    for domain in ("watering", "nutrition", "pests", "disease", "toxicity"):
        domain_aspects = {
            aspect
            for aspect in policy.required_aspects
            if REQUIRED_ASPECT_METADATA[aspect].domain == domain
        }
        assert len({group_by_aspect[aspect] for aspect in domain_aspects}) == 1


def test_policy_v1_result_exactly_partitions_all_required_aspects() -> None:
    required = sorted(aspect.value for aspect in ENRICHMENT_POLICY_V1.required_aspects)
    complete = EnrichmentJobResult(
        outcome="complete",
        policy_version=1,
        covered_aspects=required,
        missing_aspects=[],
        covered_count=len(required),
        missing_count=0,
    )

    assert complete.covered_count == 17
    with pytest.raises(ValueError, match="exactly partition"):
        EnrichmentJobResult(
            outcome="partial",
            policy_version=1,
            covered_aspects=required[:1],
            missing_aspects=required[1:-1],
            covered_count=1,
            missing_count=15,
            limitations=[EnrichmentLimitation.missing_required_aspects],
        )
    with pytest.raises(ValueError, match="exactly partition"):
        EnrichmentJobResult(
            outcome="complete",
            policy_version=1,
            covered_aspects=required[:1],
            missing_aspects=[],
            covered_count=1,
            missing_count=0,
        )


def test_changed_policy_semantics_require_a_new_version() -> None:
    changed_same_version = replace(ENRICHMENT_POLICY_V1, max_searches=6)
    changed_new_version = replace(changed_same_version, version=2)

    assert policy_change_requires_version_bump(ENRICHMENT_POLICY_V1, changed_same_version)
    assert not policy_change_requires_version_bump(ENRICHMENT_POLICY_V1, changed_new_version)


def test_workflow_aspect_fields_are_distinct_and_derive_missing_sets() -> None:
    required = ENRICHMENT_POLICY_V1.required_aspects
    local = frozenset({RequiredAspect.light_exposure})
    final = local | {RequiredAspect.soil_drainage}

    workflow = EnrichmentWorkflowAspects.from_coverage(
        required_aspects=required,
        local_covered_aspects=local,
        final_covered_aspects=final,
    )

    assert workflow.acquisition_aspects == required - local
    assert workflow.final_covered_aspects == final
    assert workflow.final_missing_aspects == required - final


def test_active_and_run_idempotency_keys_are_stable_and_separate() -> None:
    identity = _identity()
    run_id = UUID("11111111-1111-1111-1111-111111111111")

    active = build_active_work_key(identity, 1)
    run = build_run_idempotency_key(identity, 1, run_id)

    assert active == build_active_work_key(identity, 1)
    assert run == build_run_idempotency_key(identity, 1, str(run_id))
    assert active != run
    assert build_active_work_key(identity, 2) != active
    assert build_run_idempotency_key(identity, 1, UUID(int=2)) != run
