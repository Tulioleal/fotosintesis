from collections import defaultdict
from uuid import UUID, uuid4

from sqlalchemy import delete, func, insert, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.schemas import GardenPlantCard
from app.auth.tables import (
    garden_plants,
    identification_candidates,
    identification_images,
    knowledge_chunks,
    plant_profiles,
)
from app.db.repository import RepositoryBase
from app.profile_garden.schemas import (
    GardenPlantCreate,
    GardenPlantResponse,
    PlantProfileResponse,
    ProfileAlias,
    ProfileSource,
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
    ) -> PlantProfileResponse:
        existing = await self._get_profile_row(scientific_name)
        if existing is None:
            profile_id = await self._create_profile(scientific_name, common_name)
            existing = await self._get_profile_row_by_id(profile_id)
        if existing is None:
            raise ValueError("Unable to create plant profile")
        return _profile_from_row(existing, region=region, country=country, language=language)

    async def save_garden_plant(
        self, *, user_id: UUID, payload: GardenPlantCreate
    ) -> GardenPlantResponse | None:
        candidate = await self.confirmed_candidate(payload.confirmed_candidate_id, user_id)
        if candidate is None:
            return None
        scientific_name = candidate.accepted_scientific_name or candidate.suggested_scientific_name
        profile = await self.get_or_create_profile(
            scientific_name=scientific_name,
            common_name=candidate.common_name,
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
        return [_garden_from_row(row._mapping) for row in rows]

    async def get_garden_plant(self, garden_id: UUID, user_id: UUID) -> GardenPlantResponse | None:
        row = (
            await self.session.execute(
                select(garden_plants, plant_profiles)
                .join(plant_profiles, plant_profiles.c.id == garden_plants.c.profile_id)
                .where(garden_plants.c.id == garden_id, garden_plants.c.user_id == user_id)
            )
        ).first()
        return _garden_from_row(row._mapping) if row else None

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

    async def _get_profile_row_by_id(self, profile_id: UUID):
        return (
            await self.session.execute(
                select(plant_profiles).where(plant_profiles.c.id == profile_id)
            )
        ).first()

    async def _create_profile(self, scientific_name: str, common_name: str | None) -> UUID:
        rows = (
            await self.session.execute(
                select(knowledge_chunks).where(
                    knowledge_chunks.c.scientific_name == scientific_name
                )
            )
        ).all()
        profile_id = uuid4()
        sections, sources, confidence, limitations, aliases = _build_profile_evidence(
            scientific_name, common_name, [row._mapping for row in rows]
        )
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
            )
        )
        await self.session.commit()
        return profile_id

    async def confirmed_candidate(self, candidate_id: UUID, user_id: UUID):
        return (
            await self.session.execute(
                select(identification_candidates)
                .join(
                    identification_images,
                    identification_images.c.id == identification_candidates.c.identification_id,
                )
                .where(
                    identification_candidates.c.id == candidate_id,
                    identification_candidates.c.validation_status == "validated",
                    identification_candidates.c.confirmed_at.is_not(None),
                    identification_images.c.user_id == user_id,
                )
            )
        ).first()

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


def _build_profile_evidence(
    scientific_name: str, common_name: str | None, chunks: list[dict]
) -> tuple:
    grouped: dict[str, list[str]] = defaultdict(list)
    sources_by_url: dict[str, dict[str, object]] = {}
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
                metadata.get("title") if isinstance(metadata, dict) else chunk["source_domain"]
            ),
            "url": chunk["source_url"],
            "domain": chunk["source_domain"],
            "confidence": float(chunk["confidence"]),
        }

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

    return sections, list(sources_by_url.values()), confidence, limitations, aliases


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
    )


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


def _garden_from_row(row) -> GardenPlantResponse:
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
    )
    return GardenPlantResponse(
        id=row[garden_plants.c.id],
        profile=profile,
        confirmed_candidate_id=row[garden_plants.c.confirmed_candidate_id],
        nickname=row[garden_plants.c.nickname],
        notes=row[garden_plants.c.notes],
        location=row[garden_plants.c.location],
        image_path=row[garden_plants.c.image_path],
        custom_data=row[garden_plants.c.custom_data],
        active_reminders=row[garden_plants.c.active_reminders],
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
