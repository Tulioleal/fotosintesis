"""Per-section version metadata for plant profiles.

Each generated profile section records the stable section identifier, its
applicable canonical aspect set, the generation policy version, the
deterministic evidence fingerprint that produced it, provenance, confidence,
limitations, and generation timestamp. Status metadata exposes whether a
section is current, stale, refreshing, or partial without leaking raw job
payloads or evidence content.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime

from app.profile_garden.fingerprint import SECTION_ASPECTS

# Closed set of refresh statuses exposed to API consumers. Metadata-only.
CURRENT = "current"
STALE = "stale"
REFRESHING = "refreshing"
PARTIAL = "partial"

REFRESH_STATUSES = {CURRENT, STALE, REFRESHING, PARTIAL}


def _utcnow() -> datetime:
    return datetime.now(UTC)


def build_section_version(
    *,
    section: str,
    fingerprint: str,
    generation_policy_version: int,
    provenance: list[dict[str, object]],
    confidence: float,
    limitations: list[str],
    status: str = CURRENT,
    generated_at: datetime | None = None,
) -> dict[str, object]:
    """Build the persisted version record for a generated section."""
    return {
        "section_id": section,
        "aspects": list(SECTION_ASPECTS.get(section, ())),
        "policy_version": generation_policy_version,
        "fingerprint": fingerprint,
        "provenance": provenance,
        "confidence": confidence,
        "limitations": limitations,
        "status": status,
        "generated_at": (generated_at or _utcnow()).isoformat(),
    }


def refresh_status(section_version: Mapping[str, object] | None) -> str:
    """Return the effective refresh status for a section version.

    A section without any recorded version (a legacy profile section) is
    treated as unknown, which the API surfaces as stale so reconciliation can
    evaluate it. A recorded version reports its own status.
    """
    if section_version is None:
        return STALE
    status = section_version.get("status")
    if status in REFRESH_STATUSES:
        return status
    return CURRENT


__all__ = [
    "CURRENT",
    "PARTIAL",
    "REFRESHING",
    "REFRESH_STATUSES",
    "STALE",
    "build_section_version",
    "refresh_status",
]
