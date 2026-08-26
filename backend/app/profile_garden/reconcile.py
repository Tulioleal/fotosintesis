"""Bounded reconciliation of legacy profiles without evidence fingerprints.

Profiles that predate evidence fingerprints are treated as unknown rather than
automatically current. Reconciliation evaluates their sections against current
evidence coverage in bounded batches, prioritizes sections containing
insufficient-evidence fallback text for refresh, and keeps existing sourced
sections visible until a replacement succeeds. Historical profile text and
provenance are never discarded.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import cast, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.tables import plant_profiles
from app.enrichment.identity import CanonicalSpeciesIdentity
from app.enrichment.policy import CURRENT_ENRICHMENT_POLICY_VERSION
from app.profile_garden.fingerprint import SECTION_ASPECTS
from app.profile_garden.signals import enqueue_profile_refresh

logger = logging.getLogger(__name__)

INSUFFICIENT_PREFIX = "Insufficient evidence"


class LegacyReconciliationService:
    """Evaluate fingerprint-less profiles and schedule targeted refreshes."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def reconcile_batch(self, *, limit: int = 50) -> dict[str, object]:
        """Process a bounded batch of legacy profiles.

        Returns a summary of how many profiles were evaluated and how many
        refresh signals were enqueued. Each signal is keyed by species identity
        and evidence fingerprint so duplicate work collapses.
        """
        rows = (
            await self.session.execute(
                select(plant_profiles)
                .where(
                    or_(
                        plant_profiles.c.section_versions.is_(None),
                        cast(plant_profiles.c.section_versions, sa.String) == "{}",
                    )
                )
                .limit(limit)
            )
        ).all()

        evaluated = 0
        signalled = 0
        for row in rows:
            evaluated += 1
            insufficient_sections = _insufficient_sections(row.sections)
            if not insufficient_sections:
                continue
            aspects = _aspects_for_sections(insufficient_sections)
            if not aspects:
                continue
            try:
                identity = CanonicalSpeciesIdentity(
                    accepted_gbif_key=row.accepted_gbif_key,
                    normalized_binomial=row.normalized_binomial or row.scientific_name,
                    taxonomy_validated=True,
                )
            except ValueError:
                logger.warning("legacy profile skipped: no valid identity", extra={"ctx_profile": str(row.id)})
                continue
            evidence = _evidence_for_sections(row, insufficient_sections)
            try:
                await enqueue_profile_refresh(
                    self.session,
                    identity=identity,
                    changed_aspects=sorted(aspects),
                    generation_policy_version=CURRENT_ENRICHMENT_POLICY_VERSION,
                    evidence=evidence,
                )
                signalled += 1
            except Exception:
                logger.exception("legacy reconciliation signal failed", extra={"ctx_profile": str(row.id)})
        await self.session.commit()
        return {"evaluated": evaluated, "signalled": signalled}


def _insufficient_sections(sections: dict) -> list[str]:
    if not isinstance(sections, dict):
        return []
    result = []
    for section, items in sections.items():
        texts = items if isinstance(items, list) else []
        if any(
            isinstance(text, str) and text.startswith(INSUFFICIENT_PREFIX)
            for text in texts
        ):
            result.append(section)
    return result


def _aspects_for_sections(sections: Sequence[str]) -> set[str]:
    aspects: set[str] = set()
    for section in sections:
        aspects.update(SECTION_ASPECTS.get(section, ()))
    return aspects


def _evidence_for_sections(row, sections: Sequence[str]) -> list[dict[str, object]]:
    """Return a placeholder evidence list for fingerprint idempotency.

    A legacy profile without a fingerprint has no recorded per-section
    evidence identifiers; we derive a stable, deterministic identifier from
    the profile identity and the affected section set so repeated
    reconciliation of the same profile collapses into one refresh job.
    """
    raw = f"legacy:{row.id}:{','.join(sorted(sections))}"
    return [
        {
            "source_url": f"legacy:{row.id}",
            "source_version": raw,
        }
    ]


__all__ = ["LegacyReconciliationService"]
