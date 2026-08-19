"""Section-level profile refresh from the latest accepted evidence.

A refresh regenerates only the sections that depend on changed canonical
aspects. The regenerated sections replace the prior active versions atomically
in a single update; if regeneration fails the previous section versions remain
readable and are surfaced as stale.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.tables import plant_profiles
from app.profile_garden.fingerprint import sections_for_aspects
from app.profile_garden.repository import (
    SECTION_TOPICS,
    PlantProfileGardenRepository,
    _build_profile_evidence,
)
from app.profile_garden.versions import STALE


class ProfileRefreshError(RuntimeError):
    pass


class ProfileRefreshService:
    """Regenerate stale profile sections from the latest accepted evidence."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = PlantProfileGardenRepository(session)

    async def refresh_sections(
        self,
        *,
        species: dict[str, object],
        changed_aspects: list[str],
        generation_policy_version: int,
    ) -> dict[str, object]:
        """Refresh the affected sections of a species profile.

        Returns a result mapping with ``regenerated`` and ``stale`` section
        lists. Raises ``ProfileRefreshError`` when no profile exists for the
        species.
        """
        canonical_species_key = str(species.get("canonical_species_key") or "")
        normalized_binomial = str(species.get("normalized_binomial") or "")
        row = await self._find_profile(
            canonical_species_key=canonical_species_key,
            normalized_binomial=normalized_binomial,
        )
        if row is None:
            raise ProfileRefreshError("no profile exists for the species")

        affected = set(sections_for_aspects(changed_aspects))
        affected = affected & set(SECTION_TOPICS)
        if not affected:
            return {"regenerated": [], "stale": []}

        try:
            rows = await self.repository._profile_evidence_chunks(
                canonical_species_key=row.canonical_species_key,
                normalized_binomial=row.normalized_binomial,
            )
            (
                fresh_sections,
                fresh_sources,
                fresh_confidence,
                fresh_limitations,
                _aliases,
                fresh_versions,
            ) = _build_profile_evidence(
                row.scientific_name,
                row.common_name,
                [r._mapping for r in rows],
                generation_policy_version=generation_policy_version,
            )
        except Exception as exc:
            await self._mark_stale(profile_id=row.id, sections=affected)
            raise ProfileRefreshError(
                "profile refresh failed; previous sections preserved"
            ) from exc

        sections = dict(row.sections)
        versions = dict(row.section_versions or {})
        for section in affected:
            sections[section] = fresh_sections.get(section, sections.get(section, []))
            if section in fresh_versions:
                fresh_versions[section]["status"] = "current"
                versions[section] = fresh_versions[section]

        await self.session.execute(
            update(plant_profiles)
            .where(plant_profiles.c.id == row.id)
            .values(
                sections=sections,
                sources=fresh_sources,
                confidence=fresh_confidence,
                limitations=fresh_limitations,
                section_versions=versions,
                generation_policy_version=generation_policy_version,
                updated_at=datetime.now(UTC),
            )
        )
        await self.session.commit()
        return {"regenerated": sorted(affected), "stale": []}

    async def _mark_stale(self, *, profile_id: UUID, sections: set[str]) -> None:
        """Keep the previous visible version and mark it stale on failure."""
        row = (
            await self.session.execute(
                select(plant_profiles).where(plant_profiles.c.id == profile_id)
            )
        ).first()
        if row is None:
            return
        versions = dict(row.section_versions or {})
        for section in sections:
            if section in versions:
                versions[section] = dict(versions[section])
                versions[section]["status"] = STALE
        await self.session.execute(
            update(plant_profiles)
            .where(plant_profiles.c.id == profile_id)
            .values(section_versions=versions, updated_at=datetime.now(UTC))
        )
        await self.session.commit()

    async def _find_profile(self, *, canonical_species_key: str, normalized_binomial: str):
        if canonical_species_key:
            stmt = select(plant_profiles).where(
                plant_profiles.c.canonical_species_key == canonical_species_key
            )
        elif normalized_binomial:
            stmt = select(plant_profiles).where(
                plant_profiles.c.normalized_binomial == normalized_binomial
            )
        else:
            return None
        return (await self.session.execute(stmt)).first()


__all__ = ["ProfileRefreshError", "ProfileRefreshService"]
