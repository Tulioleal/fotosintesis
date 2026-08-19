"""Unit tests for profile evidence fingerprints and section-version metadata.

Covers the deterministic fingerprint computation, its independence from
retrieval order and formatting, the aspect-to-section mapping, and the
section-version refresh-status helpers.
"""

from __future__ import annotations

from app.profile_garden.fingerprint import (
    compute_evidence_fingerprint,
    fingerprint_for_section,
    sections_for_aspects,
)
from app.profile_garden.versions import (
    CURRENT,
    STALE,
    build_section_version,
    refresh_status,
)

EVIDENCE = [
    {
        "source_url": "https://example.org/monstera-care",
        "source_version": "v1",
        "aspect": "light_exposure",
    },
    {
        "source_url": "https://example.org/monstera-soil",
        "source_version": "2026-01-01",
        "aspect": "soil_drainage",
    },
]


def test_fingerprint_is_deterministic() -> None:
    a = compute_evidence_fingerprint(evidence=EVIDENCE, generation_policy_version=1)
    b = compute_evidence_fingerprint(evidence=EVIDENCE, generation_policy_version=1)
    assert a == b


def test_fingerprint_is_order_independent() -> None:
    a = compute_evidence_fingerprint(evidence=EVIDENCE, generation_policy_version=1)
    b = compute_evidence_fingerprint(
        evidence=list(reversed(EVIDENCE)),
        generation_policy_version=1,
    )
    assert a == b


def test_fingerprint_is_formatting_independent() -> None:
    # A different object ordering / formatting of the same evidence yields the
    # same fingerprint because identifiers are sorted and compactly encoded.
    reordered = [
        {"source_version": "2026-01-01", "source_url": "https://example.org/monstera-soil", "aspect": "soil_drainage"},
        {"source_url": "https://example.org/monstera-care", "source_version": "v1", "aspect": "light_exposure"},
    ]
    a = compute_evidence_fingerprint(evidence=EVIDENCE, generation_policy_version=1)
    b = compute_evidence_fingerprint(evidence=reordered, generation_policy_version=1)
    assert a == b


def test_fingerprint_changes_with_policy_version() -> None:
    a = compute_evidence_fingerprint(evidence=EVIDENCE, generation_policy_version=1)
    b = compute_evidence_fingerprint(evidence=EVIDENCE, generation_policy_version=2)
    assert a != b


def test_section_fingerprint_only_tracks_its_own_aspects() -> None:
    # The care section depends on light and soil; adding unrelated evidence
    # (e.g. pest) must not change the section's fingerprint.
    section = "care"
    base = fingerprint_for_section(
        section=section,
        evidence=EVIDENCE,
        generation_policy_version=1,
    )
    unrelated = EVIDENCE + [
        {
            "source_url": "https://example.org/monstera-pests",
            "source_version": "v9",
            "aspect": "pest_identification",
        }
    ]
    changed = fingerprint_for_section(
        section=section,
        evidence=unrelated,
        generation_policy_version=1,
    )
    assert base == changed


def test_section_fingerprint_changes_when_its_aspect_evidence_changes() -> None:
    section = "care"
    base = fingerprint_for_section(
        section=section,
        evidence=EVIDENCE,
        generation_policy_version=1,
    )
    new_evidence = EVIDENCE + [
        {
            "source_url": "https://example.org/monstera-light-updated",
            "source_version": "v2",
            "aspect": "light_exposure",
        }
    ]
    changed = fingerprint_for_section(
        section=section,
        evidence=new_evidence,
        generation_policy_version=1,
    )
    assert base != changed


def test_sections_for_aspects_maps_only_affected_sections() -> None:
    affected = sections_for_aspects(["light_exposure"])
    assert "conditions" in affected
    assert "care" in affected
    assert "pests" not in affected
    assert "diseases" not in affected


def test_refresh_status_defaults_legacy_to_stale() -> None:
    assert refresh_status(None) == STALE


def test_refresh_status_reports_recorded_status() -> None:
    version = build_section_version(
        section="care",
        fingerprint="abc",
        generation_policy_version=1,
        provenance=[],
        confidence=0.8,
        limitations=[],
        status=CURRENT,
    )
    assert refresh_status(version) == CURRENT
