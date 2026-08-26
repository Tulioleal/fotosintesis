from collections import defaultdict
from uuid import UUID, uuid4

from sqlalchemy import Text, delete, func, insert, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.schemas import GardenPlantCard
from app.auth.tables import (
    enrichment_validation_evidence,
    enrichment_validation_runs,
    garden_plants,
    identification_candidates,
    identification_images,
    knowledge_chunks,
    knowledge_document_aspect_supports,
    knowledge_documents,
    knowledge_sources,
    light_measurements,
    plant_profiles,
    reminders,
)
from app.db.repository import RepositoryBase
from app.enrichment.identity import CanonicalSpeciesIdentity
from app.enrichment.policy import CURRENT_ENRICHMENT_POLICY_VERSION
from app.knowledge.schemas import ReviewStatus
from app.profile_garden.fingerprint import fingerprint_for_section
from app.profile_garden.schemas import (
    GardenPlantCreate,
    GardenPlantResponse,
    LightSummary,
    LocalPlantSearchResult,
    PlantProfileResponse,
    ProfileAlias,
    ProfileSectionStatus,
    ProfileSource,
    ReminderSummary,
)
from app.schemas.reminders import ReminderStatus
from app.profile_garden.versions import (
    CURRENT,
    PARTIAL,
    build_section_version,
    refresh_status,
)

SECTION_TOPICS = {
    "description": "description",
    "characteristics": "characteristics",
    "conditions": "conditions",
    "care": "care",
    "pests": "pests",
    "diseases": "diseases",
    "recommendations": "recommendations",
}


def canonical_identity_fields(candidate) -> dict[str, object]:
    """Derive canonical profile identity from a confirmed candidate.

    Returns an empty mapping when the candidate has no valid normalized
    binomial, so callers keep the legacy display-name behavior.
    """
    if candidate is None:
        return {}
    try:
        identity = CanonicalSpeciesIdentity(
            accepted_gbif_key=candidate.gbif_accepted_key,
            normalized_binomial=candidate.binomial_name,
            taxonomy_validated=True,
        )
    except (TypeError, ValueError):
        return {}
    assert identity.normalized_binomial is not None
    return {
        "accepted_gbif_key": identity.accepted_gbif_key,
        "normalized_binomial": identity.normalized_binomial,
        "canonical_species_key": identity.key,
    }


class GardenImageValidationError(ValueError):
    """Raised when a save references an image the caller does not own."""


class PlantProfileGardenRepository(RepositoryBase):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_or_create_profile(
        self,
        *,
        scientific_name: str,
        common_name: str | None = None,
        region: str | None = None,
        country: str | None = None,
        language: str | None = None,
        accepted_gbif_key: int | None = None,
        normalized_binomial: str | None = None,
        canonical_species_key: str | None = None,
    ) -> PlantProfileResponse:
        for attempt in range(2):
            existing = await self._find_profile(
                scientific_name=scientific_name,
                normalized_binomial=normalized_binomial,
                canonical_species_key=canonical_species_key,
            )
            if existing is not None:
                return _profile_from_row(
                    existing, region=region, country=country, language=language
                )
            try:
                profile_id = await self._create_profile(
                    scientific_name,
                    common_name,
                    accepted_gbif_key=accepted_gbif_key,
                    normalized_binomial=normalized_binomial,
                    canonical_species_key=canonical_species_key,
                )
                existing = await self._get_profile_row_by_id(profile_id)
                if existing is not None:
                    return _profile_from_row(
                        existing, region=region, country=country, language=language
                    )
            except IntegrityError:
                # Concurrent canonical profile creation lost the unique-key
                # race; the retry re-selects the winning profile.
                if attempt == 0:
                    continue
                raise
            break
        raise ValueError("Unable to create plant profile")

    async def _find_profile(
        self,
        *,
        scientific_name: str,
        normalized_binomial: str | None,
        canonical_species_key: str | None,
    ):
        """Select an existing profile for the canonical identity.

        A profile is found only by its canonical species key when one is
        supplied. Ambiguous null-key legacy profiles are never adopted at
        runtime based on display-name equality: the 0014 migration backfilled
        only unambiguous controlled legacy rows, and remaining null-key rows
        stay unchanged. A candidate without any canonical identity (no GBIF
        key and no normalized binomial) keeps the legacy display-name lookup.
        """
        if canonical_species_key:
            return await self._get_profile_row_by_canonical(canonical_species_key)
        if not normalized_binomial:
            return await self._get_profile_row(scientific_name)
        return None

    async def save_garden_plant(
        self, *, user_id: UUID, payload: GardenPlantCreate
    ) -> GardenPlantResponse | None:
        candidate = await self.confirmed_candidate(payload.confirmed_candidate_id, user_id)
        if candidate is None:
            return None
        if payload.image_path is not None:
            await self._ensure_owned_identification_image(
                user_id=user_id,
                candidate_id=payload.confirmed_candidate_id,
                storage_path=payload.image_path,
            )
        scientific_name = candidate.accepted_scientific_name or candidate.suggested_scientific_name
        profile = await self.get_or_create_profile(
            scientific_name=scientific_name,
            common_name=candidate.common_name,
            **canonical_identity_fields(candidate),
        )
        garden_id = uuid4()
        await self.session.execute(
            insert(garden_plants).values(
                id=garden_id,
                user_id=user_id,
                profile_id=profile.id,
                confirmed_candidate_id=payload.confirmed_candidate_id,
                nickname=payload.nickname,
                notes=payload.notes,
                location=payload.location,
                image_path=payload.image_path,
                custom_data=payload.custom_data,
            )
        )
        await self.session.commit()
        return await self.get_garden_plant(garden_id, user_id)

    async def _ensure_owned_identification_image(
        self, *, user_id: UUID, candidate_id: UUID, storage_path: str
    ) -> None:
        row = (
            await self.session.execute(
                select(identification_images.c.id)
                .select_from(identification_candidates)
                .join(
                    identification_images,
                    identification_images.c.id == identification_candidates.c.identification_id,
                )
                .where(
                    identification_candidates.c.id == candidate_id,
                    identification_candidates.c.user_id == user_id,
                    identification_images.c.user_id == user_id,
                    identification_images.c.storage_path == storage_path,
                )
            )
        ).first()
        if row is None:
            raise GardenImageValidationError(
                "The provided plant image does not belong to this confirmed plant."
            )

    async def garden_plant_image_path(self, *, user_id: UUID, plant_id: UUID) -> str | None:
        """Authoritative image path for a garden plant, derived from its confirmed
        candidate's identification record so stored values can never cross owners."""
        row = (
            await self.session.execute(
                select(identification_images.c.storage_path)
                .select_from(garden_plants)
                .join(
                    identification_candidates,
                    identification_candidates.c.id == garden_plants.c.confirmed_candidate_id,
                )
                .join(
                    identification_images,
                    identification_images.c.id == identification_candidates.c.identification_id,
                )
                .where(
                    garden_plants.c.id == plant_id,
                    garden_plants.c.user_id == user_id,
                    identification_images.c.user_id == user_id,
                )
            )
        ).first()
        return row[0] if row else None

    async def list_garden_plants(
        self, *, user_id: UUID, query: str | None = None
    ) -> list[GardenPlantResponse]:
        statement = (
            select(garden_plants, plant_profiles)
            .join(plant_profiles, plant_profiles.c.id == garden_plants.c.profile_id)
            .where(garden_plants.c.user_id == user_id)
            .order_by(garden_plants.c.created_at.desc())
        )
        if query:
            pattern = f"%{query.lower()}%"
            statement = statement.where(
                or_(
                    garden_plants.c.nickname.ilike(pattern),
                    plant_profiles.c.common_name.ilike(pattern),
                    plant_profiles.c.scientific_name.ilike(pattern),
                )
            )
        rows = (await self.session.execute(statement)).all()
        plant_ids = [row._mapping[garden_plants.c.id] for row in rows]
        next_reminders = await self.next_pending_reminder_summaries(
            user_id=user_id, plant_ids=plant_ids
        )
        light_summaries = await self.latest_light_summaries(
            user_id=user_id, plant_ids=plant_ids
        )
        return [
            _garden_from_row(
                row._mapping,
                next_reminders=next_reminders,
                light_summaries=light_summaries,
            )
            for row in rows
        ]

    async def get_garden_plant(self, garden_id: UUID, user_id: UUID) -> GardenPlantResponse | None:
        row = (
            await self.session.execute(
                select(garden_plants, plant_profiles)
                .join(plant_profiles, plant_profiles.c.id == garden_plants.c.profile_id)
                .where(garden_plants.c.id == garden_id, garden_plants.c.user_id == user_id)
            )
        ).first()
        if row is None:
            return None
        mapping = row._mapping
        garden_id = mapping[garden_plants.c.id]
        next_reminders = await self.next_pending_reminder_summaries(
            user_id=user_id, plant_ids=[garden_id]
        )
        light_summaries = await self.latest_light_summaries(
            user_id=user_id, plant_ids=[garden_id]
        )
        return _garden_from_row(
            mapping,
            next_reminders=next_reminders,
            light_summaries=light_summaries,
        )

    async def next_pending_reminder_summaries(
        self, *, user_id: UUID, plant_ids: list[UUID] | None = None
    ) -> dict[UUID, ReminderSummary]:
        """Return the earliest pending reminder per garden plant in one query.

        Uses a row-number window instead of Postgres ``DISTINCT ON`` so the
        same query runs on the SQLite test backend and the production
        Postgres backend without per-plant requests.
        """
        subquery = (
            select(
                reminders.c.garden_plant_id,
                reminders.c.id,
                reminders.c.action,
                reminders.c.due_at,
                reminders.c.timezone,
                func.row_number()
                .over(
                    partition_by=reminders.c.garden_plant_id,
                    order_by=reminders.c.due_at.asc(),
                )
                .label("_row_number"),
            )
            .where(
                reminders.c.user_id == user_id,
                reminders.c.status == ReminderStatus.pending.value,
            )
            .subquery()
        )
        statement = select(subquery).where(subquery.c._row_number == 1)
        if plant_ids is not None:
            statement = statement.where(subquery.c.garden_plant_id.in_(plant_ids))
        rows = (await self.session.execute(statement)).all()
        return {
            row.garden_plant_id: ReminderSummary(
                id=row.id,
                action=row.action,
                due_at=row.due_at,
                timezone=row.timezone,
            )
            for row in rows
        }

    async def latest_light_summaries(
        self, *, user_id: UUID, plant_ids: list[UUID] | None = None
    ) -> dict[UUID, LightSummary]:
        """Return the latest light measurement per garden plant in one query.

        Row-number window keeps the batched selection portable across the
        SQLite test backend and the production Postgres backend.
        """
        subquery = (
            select(
                light_measurements.c.garden_plant_id,
                light_measurements.c.id,
                light_measurements.c.classification,
                light_measurements.c.lux,
                light_measurements.c.reliability,
                light_measurements.c.source,
                light_measurements.c.measured_at,
                func.row_number()
                .over(
                    partition_by=light_measurements.c.garden_plant_id,
                    order_by=light_measurements.c.measured_at.desc(),
                )
                .label("_row_number"),
            )
            .where(
                light_measurements.c.user_id == user_id,
                light_measurements.c.garden_plant_id.is_not(None),
            )
            .subquery()
        )
        statement = select(subquery).where(subquery.c._row_number == 1)
        if plant_ids is not None:
            statement = statement.where(subquery.c.garden_plant_id.in_(plant_ids))
        rows = (await self.session.execute(statement)).all()
        return {
            row.garden_plant_id: LightSummary(
                id=row.id,
                classification=row.classification,
                lux=row.lux,
                reliability=row.reliability,
                source=row.source,
                measured_at=row.measured_at,
            )
            for row in rows
        }

    async def delete_garden_plant(
        self, *, garden_id: UUID, user_id: UUID, confirm_reminders: bool
    ) -> str | None:
        plant = (
            await self.session.execute(
                select(garden_plants).where(
                    garden_plants.c.id == garden_id,
                    garden_plants.c.user_id == user_id,
                )
            )
        ).first()
        if plant is None:
            return None
        if plant.active_reminders > 0 and not confirm_reminders:
            return "reminder_confirmation_required"
        await self.session.execute(delete(garden_plants).where(garden_plants.c.id == garden_id))
        await self.session.commit()
        return "deleted"

    async def _get_profile_row(self, scientific_name: str):
        return (
            await self.session.execute(
                select(plant_profiles).where(plant_profiles.c.scientific_name == scientific_name)
            )
        ).first()

    async def _get_profile_row_by_canonical(self, canonical_species_key: str):
        return (
            await self.session.execute(
                select(plant_profiles).where(
                    plant_profiles.c.canonical_species_key == canonical_species_key
                )
            )
        ).first()

    async def _get_profile_row_by_id(self, profile_id: UUID):
        return (
            await self.session.execute(
                select(plant_profiles).where(plant_profiles.c.id == profile_id)
            )
        ).first()

    async def _create_profile(
        self,
        scientific_name: str,
        common_name: str | None,
        *,
        accepted_gbif_key: int | None = None,
        normalized_binomial: str | None = None,
        canonical_species_key: str | None = None,
    ) -> UUID:
        rows = await self._profile_evidence_chunks(
            canonical_species_key=canonical_species_key,
            normalized_binomial=normalized_binomial,
        )
        profile_id = uuid4()
        (
            sections,
            sources,
            confidence,
            limitations,
            aliases,
            section_versions,
        ) = _build_profile_evidence(
            scientific_name,
            common_name,
            [row._mapping for row in rows],
            generation_policy_version=CURRENT_ENRICHMENT_POLICY_VERSION,
        )
        try:
            await self.session.execute(
                insert(plant_profiles).values(
                    id=profile_id,
                    scientific_name=scientific_name,
                    common_name=common_name,
                    aliases=aliases,
                    sections=sections,
                    sources=sources,
                    confidence=confidence,
                    limitations=limitations,
                    accepted_gbif_key=accepted_gbif_key,
                    normalized_binomial=normalized_binomial,
                    canonical_species_key=canonical_species_key,
                    generation_policy_version=CURRENT_ENRICHMENT_POLICY_VERSION,
                    section_versions=section_versions,
                )
            )
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            raise
        return profile_id

    async def _profile_evidence_chunks(
        self, *, canonical_species_key: str | None, normalized_binomial: str | None
    ) -> list:
        """Gather snapshot evidence from canonical enrichment documents plus
        compatible legacy chunks by normalized binomial.

        Enrichment evidence is selected by canonical species key only; the
        authority-bearing accepted display name is never used to search
        enrichment evidence. A canonical document is eligible for a new
        snapshot only when it has trusted source provenance, an eligible
        (auto-ingested) review state, at least one accepted individual aspect
        support, and applicable validation provenance. Legacy chunks are used
        only when no canonical identity exists. Chunks are deduplicated by
        stable chunk id.
        """
        rows: list = []
        seen: set[UUID] = set()
        if canonical_species_key:
            canonical_rows = (
                await self.session.execute(
                    select(
                        knowledge_chunks,
                        knowledge_document_aspect_supports.c.aspect.label(
                            "supported_aspect"
                        ),
                        enrichment_validation_runs.c.covered_aspects.label(
                            "validation_covered_aspects"
                        ),
                        knowledge_documents.c.source_version.label("source_version"),
                        knowledge_documents.c.canonical_source_url.label(
                            "canonical_source_url"
                        ),
                    )
                    .join(
                        knowledge_documents,
                        knowledge_documents.c.id == knowledge_chunks.c.document_id,
                    )
                    .join(
                        knowledge_sources,
                        knowledge_sources.c.document_id == knowledge_documents.c.id,
                    )
                    .join(
                        knowledge_document_aspect_supports,
                        knowledge_document_aspect_supports.c.document_id
                        == knowledge_documents.c.id,
                    )
                    .join(
                        enrichment_validation_evidence,
                        enrichment_validation_evidence.c.document_id
                        == knowledge_documents.c.id,
                    )
                    .join(
                        enrichment_validation_runs,
                        enrichment_validation_runs.c.id
                        == enrichment_validation_evidence.c.validation_run_id,
                    )
                    .where(
                        knowledge_documents.c.canonical_species_key
                        == canonical_species_key,
                        knowledge_documents.c.review_status
                        == ReviewStatus.auto_ingested.value,
                        knowledge_chunks.c.review_status
                        == ReviewStatus.auto_ingested.value,
                        knowledge_document_aspect_supports.c.review_status
                        == ReviewStatus.auto_ingested.value,
                        knowledge_sources.c.validation_status == "trusted",
                        enrichment_validation_runs.c.taxonomy_provenance_id
                        == knowledge_documents.c.taxonomy_provenance_id,
                        enrichment_validation_runs.c.answerability_status.in_(
                            ["full", "partial"]
                        ),
                    )
                )
            ).all()
            for row in canonical_rows:
                mapping = row._mapping
                supported_aspect = mapping["supported_aspect"]
                covered_aspects = mapping["validation_covered_aspects"]

                if not isinstance(covered_aspects, list):
                    continue
                if supported_aspect not in covered_aspects:
                    continue

                chunk_id = mapping[knowledge_chunks.c.id]
                if chunk_id in seen:
                    continue

                seen.add(chunk_id)
                rows.append(row)
        elif normalized_binomial:
            legacy = (
                await self.session.execute(
                    select(knowledge_chunks)
                    .join(
                        knowledge_documents,
                        knowledge_documents.c.id == knowledge_chunks.c.document_id,
                    )
                    .where(
                        knowledge_chunks.c.scientific_name == normalized_binomial,
                        knowledge_documents.c.canonical_species_key.is_(None),
                    )
                )
            ).fetchall()
            for row in legacy:
                if row.id not in seen:
                    seen.add(row.id)
                    rows.append(row)
        return rows

    async def confirmed_candidate(self, candidate_id: UUID, user_id: UUID):
        return (
            await self.session.execute(
                select(identification_candidates)
                .add_columns(identification_images.c.storage_path.label("image_path"))
                .outerjoin(
                    identification_images,
                    identification_images.c.id == identification_candidates.c.identification_id,
                )
                .where(
                    identification_candidates.c.id == candidate_id,
                    identification_candidates.c.validation_status == "validated",
                    identification_candidates.c.confirmed_at.is_not(None),
                    or_(
                        identification_candidates.c.user_id == user_id,
                        identification_images.c.user_id == user_id,
                    ),
                )
            )
        ).first()

    async def search_local_profiles(self, query: str, limit: int = 12) -> list[LocalPlantSearchResult]:
        term = query.strip()
        if not term:
            return []
        pattern = f"%{term}%"

        rows = (
            await self.session.execute(
                select(
                    plant_profiles.c.id,
                    plant_profiles.c.scientific_name,
                    plant_profiles.c.common_name,
                    plant_profiles.c.normalized_binomial,
                    plant_profiles.c.aliases,
                    plant_profiles.c.sections,
                )
                .where(
                    or_(
                        plant_profiles.c.scientific_name.ilike(pattern),
                        plant_profiles.c.normalized_binomial.ilike(pattern),
                        plant_profiles.c.common_name.ilike(pattern),
                        plant_profiles.c.aliases.cast(Text).ilike(pattern),
                    )
                )
                .order_by(plant_profiles.c.scientific_name)
                .limit(limit)
            )
        ).all()

        results: list[LocalPlantSearchResult] = []
        for row in rows:
            mapping = row._mapping
            scientific = mapping[plant_profiles.c.scientific_name]
            common = mapping[plant_profiles.c.common_name]
            binomial = mapping[plant_profiles.c.normalized_binomial]
            aliases = mapping[plant_profiles.c.aliases] or []
            sections = mapping[plant_profiles.c.sections] or {}

            matched_field, matched_value = _resolve_local_match(
                term, scientific, common, binomial, aliases
            )

            results.append(
                LocalPlantSearchResult(
                    profile_id=mapping[plant_profiles.c.id],
                    scientific_name=scientific,
                    common_name=common,
                    binomial_name=binomial,
                    matched_field=matched_field,
                    matched_value=matched_value,
                    has_evidence=bool(sections),
                )
            )
        return results

    async def count_garden_plants(self, *, user_id: UUID) -> int:
        value = await self.session.scalar(
            select(func.count())
            .select_from(garden_plants)
            .where(garden_plants.c.user_id == user_id)
        )
        return int(value or 0)

    async def list_recent_garden_plants(
        self, *, user_id: UUID, limit: int = 8
    ) -> list[GardenPlantCard]:
        statement = (
            select(garden_plants, plant_profiles)
            .join(plant_profiles, plant_profiles.c.id == garden_plants.c.profile_id)
            .where(garden_plants.c.user_id == user_id)
            .order_by(
                garden_plants.c.created_at.desc(),
                garden_plants.c.id,
            )
            .limit(limit)
        )
        rows = (await self.session.execute(statement)).all()
        return [_garden_card_from_row(row._mapping) for row in rows]


def _resolve_local_match(
    term: str,
    scientific_name: str | None,
    common_name: str | None,
    binomial_name: str | None,
    aliases: list,
) -> tuple[str, str]:
    """Determine which field a profile matched on, in priority order."""
    lowered = term.casefold()
    if scientific_name and lowered in scientific_name.casefold():
        return ("scientific_name", scientific_name)
    if binomial_name and lowered in binomial_name.casefold():
        return ("binomial_name", binomial_name)
    if common_name and lowered in common_name.casefold():
        return ("common_name", common_name)
    if isinstance(aliases, list):
        for alias in aliases:
            if not isinstance(alias, dict):
                continue
            name = alias.get("name")
            if isinstance(name, str) and lowered in name.casefold():
                return ("alias", name)
    return ("scientific_name", scientific_name or "")


def _build_profile_evidence(
    scientific_name: str,
    common_name: str | None,
    chunks: list[dict],
    *,
    generation_policy_version: int,
) -> tuple:
    grouped: dict[str, list[str]] = defaultdict(list)
    sources_by_url: dict[str, dict[str, object]] = {}
    section_evidence: dict[str, list[dict[str, object]]] = defaultdict(list)
    confidences = []
    aliases = []
    if common_name:
        aliases.append({"name": common_name, "language": "general"})

    for chunk in chunks:
        topic = str(chunk["topic"])
        section = topic if topic in SECTION_TOPICS else _section_for_topic(topic)
        grouped[section].append(chunk["content"])
        confidences.append(float(chunk["confidence"]))
        metadata = chunk["metadata"] or {}
        for alias in metadata.get("aliases", []) if isinstance(metadata, dict) else []:
            if isinstance(alias, dict) and alias.get("name"):
                aliases.append(alias)
        sources_by_url[chunk["source_url"]] = {
            "title": (
                metadata.get("title")
                if isinstance(metadata, dict) and metadata.get("title")
                else chunk["source_domain"]
            ),
            "url": chunk["source_url"],
            "domain": chunk["source_domain"],
            "confidence": float(chunk["confidence"]),
        }
        section_evidence[section].append(
            {
                "source_url": chunk.get("canonical_source_url")
                or chunk["source_url"],
                "source_version": chunk.get("source_version") or "",
                "aspect": chunk.get("supported_aspect"),
            }
        )

    sections = {key: grouped.get(key, [])[:3] for key in SECTION_TOPICS}
    for key, fallback in SECTION_TOPICS.items():
        if not sections[key]:
            sections[key] = [f"Insufficient evidence for {fallback} of {scientific_name}."]

    confidence = round(sum(confidences) / len(confidences), 2) if confidences else 0.35
    limitations = []
    if not chunks:
        limitations.append(
            "Profile generated with limited RAG evidence; "
            "avoid critical care decisions without reviewing additional sources."
        )
    if confidence < 0.7:
        limitations.append(
            "Partial confidence: the recommendations are presented as orientative, not categorical."
        )

    section_versions = _build_section_versions(
        sections,
        section_evidence,
        confidence=confidence,
        limitations=limitations,
        generation_policy_version=generation_policy_version,
    )

    return sections, list(sources_by_url.values()), confidence, limitations, aliases, section_versions


def _build_section_versions(
    sections: dict[str, list[str]],
    section_evidence: dict[str, list[dict[str, object]]],
    *,
    confidence: float,
    limitations: list[str],
    generation_policy_version: int,
) -> dict[str, dict[str, object]]:
    """Record a version per section with its deterministic fingerprint.

    A section backed by real evidence is ``current``. A section whose content
    is the insufficient-evidence fallback is recorded as ``partial`` so the
    reconciliation pass can prioritize it. Sections without any evidence are
    still recorded with a fingerprint so profile creation is complete.
    """
    versions: dict[str, dict[str, object]] = {}
    for section, fallback_label in SECTION_TOPICS.items():
        evidence = section_evidence.get(section, [])
        fingerprint = fingerprint_for_section(
            section=section,
            evidence=evidence,
            generation_policy_version=generation_policy_version,
        )
        fallback = len(evidence) == 0
        status = PARTIAL if fallback else CURRENT
        provenance = [
            {"url": str(item["source_url"]), "domain": _domain_for(item)}
            for item in evidence
        ]
        section_limits = list(limitations)
        if fallback:
            section_limits.append(
                f"Insufficient evidence for {fallback_label} of this species."
            )
        versions[section] = build_section_version(
            section=section,
            fingerprint=fingerprint,
            generation_policy_version=generation_policy_version,
            provenance=provenance,
            confidence=confidence,
            limitations=section_limits,
            status=status,
        )
    return versions


def _domain_for(item: dict[str, object]) -> str:
    url = str(item.get("source_url") or "")
    return url.split("/")[2] if url.startswith(("http://", "https://")) and "/" in url else ""


def _section_for_topic(topic: str) -> str:
    lowered = topic.lower()
    for key in SECTION_TOPICS:
        if key in lowered:
            return key
    return "description"


def _profile_from_row(
    row, *, region: str | None, country: str | None, language: str | None
) -> PlantProfileResponse:
    aliases = [ProfileAlias.model_validate(alias) for alias in row.aliases]
    selected_alias = _select_alias(aliases, region=region, country=country, language=language)
    return PlantProfileResponse(
        id=row.id,
        scientific_name=row.scientific_name,
        common_name=row.common_name,
        selected_alias=selected_alias or row.common_name,
        aliases=aliases,
        sections=row.sections,
        sources=[ProfileSource.model_validate(source) for source in row.sources],
        confidence=row.confidence,
        limitations=row.limitations,
        accepted_gbif_key=row.accepted_gbif_key,
        binomial_name=row.normalized_binomial,
        canonical_species_key=row.canonical_species_key,
        generation_policy_version=row.generation_policy_version,
        section_status=_section_status(row.section_versions),
    )


def _section_status(section_versions: dict) -> list[ProfileSectionStatus]:
    """Build per-section freshness metadata from the persisted versions.

    Sections without a recorded version (legacy profiles) surface as stale so
    reads can identify them without blocking navigation.
    """
    versions = section_versions or {}
    statuses: list[ProfileSectionStatus] = []
    for section in SECTION_TOPICS:
        version = versions.get(section) if isinstance(versions, dict) else None
        status = refresh_status(version)
        statuses.append(
            ProfileSectionStatus(
                section=section,
                status=status,
                policy_version=(
                    version.get("policy_version")
                    if isinstance(version, dict)
                    else None
                ),
                generated_at=_parse_iso(version.get("generated_at"))
                if isinstance(version, dict)
                else None,
            )
        )
    return statuses


def _parse_iso(value: object):
    if not isinstance(value, str) or not value:
        return None
    try:
        from datetime import datetime

        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _select_alias(
    aliases: list[ProfileAlias], *, region: str | None, country: str | None, language: str | None
) -> str | None:
    for field, value in (("region", region), ("country", country), ("language", language)):
        if not value:
            continue
        for alias in aliases:
            if (getattr(alias, field) or "").lower() == value.lower():
                return alias.name
    return aliases[0].name if aliases else None


def _garden_from_row(
    row,
    *,
    next_reminders: dict[UUID, ReminderSummary] | None = None,
    light_summaries: dict[UUID, LightSummary] | None = None,
) -> GardenPlantResponse:
    profile = PlantProfileResponse(
        id=row[plant_profiles.c.id],
        scientific_name=row[plant_profiles.c.scientific_name],
        common_name=row[plant_profiles.c.common_name],
        selected_alias=_select_alias(
            [ProfileAlias.model_validate(alias) for alias in row[plant_profiles.c.aliases]],
            region=None,
            country=None,
            language=None,
        )
        or row[plant_profiles.c.common_name],
        aliases=[ProfileAlias.model_validate(alias) for alias in row[plant_profiles.c.aliases]],
        sections=row[plant_profiles.c.sections],
        sources=[ProfileSource.model_validate(source) for source in row[plant_profiles.c.sources]],
        confidence=row[plant_profiles.c.confidence],
        limitations=row[plant_profiles.c.limitations],
        accepted_gbif_key=row[plant_profiles.c.accepted_gbif_key],
        binomial_name=row[plant_profiles.c.normalized_binomial],
        canonical_species_key=row[plant_profiles.c.canonical_species_key],
        generation_policy_version=row[plant_profiles.c.generation_policy_version],
        section_status=_section_status(row[plant_profiles.c.section_versions]),
    )
    garden_id = row[garden_plants.c.id]
    return GardenPlantResponse(
        id=garden_id,
        profile=profile,
        confirmed_candidate_id=row[garden_plants.c.confirmed_candidate_id],
        nickname=row[garden_plants.c.nickname],
        notes=row[garden_plants.c.notes],
        location=row[garden_plants.c.location],
        image_path=row[garden_plants.c.image_path],
        custom_data=row[garden_plants.c.custom_data],
        active_reminders=row[garden_plants.c.active_reminders],
        next_reminder=next_reminders.get(garden_id) if next_reminders else None,
        light_summary=light_summaries.get(garden_id) if light_summaries else None,
        created_at=row[garden_plants.c.created_at],
    )


def _garden_card_from_row(row) -> GardenPlantCard:
    common = row[plant_profiles.c.common_name]
    return GardenPlantCard(
        id=row[garden_plants.c.id],
        scientific_name=row[plant_profiles.c.scientific_name],
        common_name=common,
        nickname=row[garden_plants.c.nickname],
        image_path=row[garden_plants.c.image_path],
        location=row[garden_plants.c.location],
        active_reminders=row[garden_plants.c.active_reminders],
        created_at=row[garden_plants.c.created_at],
    )
