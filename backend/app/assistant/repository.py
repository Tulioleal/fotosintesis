from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import and_, desc, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.tables import (
    conversation_messages,
    conversations,
    garden_plants,
    identification_candidates,
    identification_images,
    light_measurements,
    plant_profiles,
    reminders,
)
from app.db.repository import RepositoryBase
from app.scheduling.timezone import local_datetime_to_utc, resolve_timezone


class AssistantRepository(RepositoryBase):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_or_create_conversation(
        self, *, user_id: UUID, conversation_id: UUID | None, title: str
    ) -> UUID:
        if conversation_id is not None:
            row = (
                await self.session.execute(
                    select(conversations.c.id).where(
                        conversations.c.id == conversation_id,
                        conversations.c.user_id == user_id,
                    )
                )
            ).first()
            if row is not None:
                return conversation_id

        new_id = uuid4()
        await self.session.execute(
            insert(conversations).values(id=new_id, user_id=user_id, title=title[:240])
        )
        return new_id

    async def add_message(
        self, *, conversation_id: UUID, role: str, content: str, metadata: dict | None = None
    ) -> None:
        await self.session.execute(
            insert(conversation_messages).values(
                id=uuid4(),
                conversation_id=conversation_id,
                role=role,
                content=content,
                metadata=metadata or {},
            )
        )
        await self.session.execute(
            update(conversations)
            .where(conversations.c.id == conversation_id)
            .values(updated_at=datetime.now(timezone.utc))
        )

    async def list_garden(self, *, user_id: UUID) -> list[dict]:
        rows = (
            await self.session.execute(
                select(garden_plants, plant_profiles, identification_candidates)
                .join(plant_profiles, plant_profiles.c.id == garden_plants.c.profile_id)
                .outerjoin(
                    identification_candidates,
                    identification_candidates.c.id
                    == garden_plants.c.confirmed_candidate_id,
                )
                .where(garden_plants.c.user_id == user_id)
                .order_by(desc(garden_plants.c.created_at))
            )
        ).all()
        result: list[dict] = []
        for row in rows:
            garden = row._mapping[garden_plants.c.id]
            row._mapping[plant_profiles.c.id]
            candidate = row._mapping.get(identification_candidates.c.id)
            entry = {
                "id": garden,
                "nickname": row._mapping[garden_plants.c.nickname],
                "location": row._mapping[garden_plants.c.location],
                "scientific_name": row._mapping[plant_profiles.c.scientific_name],
                "common_name": row._mapping[plant_profiles.c.common_name],
            }
            if (
                candidate is not None
                and row._mapping.get(identification_candidates.c.validation_status) == "validated"
                and row._mapping.get(identification_candidates.c.confirmed_at) is not None
            ):
                from app.enrichment.identity import CanonicalSpeciesIdentity

                try:
                    identity = CanonicalSpeciesIdentity(
                        accepted_gbif_key=row._mapping.get(
                            identification_candidates.c.gbif_accepted_key
                        ),
                        normalized_binomial=row._mapping.get(
                            identification_candidates.c.binomial_name
                        ),
                        taxonomy_validated=True,
                    )
                    entry["accepted_gbif_key"] = identity.accepted_gbif_key
                    entry["normalized_binomial"] = identity.normalized_binomial
                    entry["canonical_species_key"] = identity.key
                except ValueError:
                    pass
            result.append(entry)
        return result

    async def create_reminder(
        self,
        *,
        user_id: UUID,
        garden_plant_id: UUID,
        action: str,
        due_at: datetime,
        recurrence: str | None,
        justification: str | None,
        timezone: str | None = None,
    ) -> UUID:
        plant = (
            await self.session.execute(
                select(garden_plants.c.id).where(
                    garden_plants.c.id == garden_plant_id,
                    garden_plants.c.user_id == user_id,
                )
            )
        ).first()
        if plant is None:
            raise ValueError("The selected plant does not exist in your garden.")

        reminder_id = uuid4()
        zone = resolve_timezone(timezone)
        due_at_utc = (
            local_datetime_to_utc(due_at.date(), due_at.time(), zone)
            if zone is not None
            else due_at
        )
        await self.session.execute(
            insert(reminders).values(
                id=reminder_id,
                user_id=user_id,
                garden_plant_id=garden_plant_id,
                action=action,
                due_at=due_at_utc,
                recurrence=recurrence,
                suggestion_justification=justification,
                timezone=timezone,
            )
        )
        await self.session.execute(
            update(garden_plants)
            .where(garden_plants.c.id == garden_plant_id)
            .values(active_reminders=garden_plants.c.active_reminders + 1)
        )
        await self.session.commit()
        return reminder_id

    async def latest_light_measurement(
        self, *, user_id: UUID, garden_plant_id: UUID | None
    ) -> dict | None:
        conditions = [light_measurements.c.user_id == user_id]
        if garden_plant_id is not None:
            conditions.append(light_measurements.c.garden_plant_id == garden_plant_id)
        row = (
            await self.session.execute(
                select(light_measurements)
                .where(and_(*conditions))
                .order_by(desc(light_measurements.c.measured_at))
                .limit(1)
            )
        ).first()
        return dict(row._mapping) if row else None

    async def resolve_candidate_context(
        self, *, user_id: UUID, candidate_id: UUID
    ) -> dict | None:
        """Resolve canonical species identity from the current user's own
        confirmed, taxonomically validated candidate.

        Returns ``None`` when the candidate is owned by another user, is not
        confirmed, is not taxonomically validated, or lacks a valid
        normalized binomial. A client-supplied canonical key is never trusted.
        """
        row = (
            await self.session.execute(
                select(
                    identification_candidates.c.accepted_scientific_name,
                    identification_candidates.c.suggested_scientific_name,
                    identification_candidates.c.gbif_accepted_key,
                    identification_candidates.c.binomial_name,
                    identification_candidates.c.validation_status,
                    identification_candidates.c.confirmed_at,
                )
                .join(
                    identification_images,
                    identification_images.c.id
                    == identification_candidates.c.identification_id,
                )
                .where(
                    identification_candidates.c.id == candidate_id,
                    identification_images.c.user_id == user_id,
                )
            )
        ).first()
        if row is None:
            return None
        if row._mapping["validation_status"] != "validated":
            return None
        if row._mapping["confirmed_at"] is None:
            return None
        from app.enrichment.identity import CanonicalSpeciesIdentity

        try:
            identity = CanonicalSpeciesIdentity(
                accepted_gbif_key=row._mapping["gbif_accepted_key"],
                normalized_binomial=row._mapping["binomial_name"],
                taxonomy_validated=True,
            )
        except (TypeError, ValueError):
            return None
        assert identity.normalized_binomial is not None
        return {
            "canonical_species_key": identity.key,
            "accepted_gbif_key": identity.accepted_gbif_key,
            "normalized_binomial": identity.normalized_binomial,
            "accepted_scientific_name": (
                row._mapping["accepted_scientific_name"]
                or row._mapping["suggested_scientific_name"]
            ),
        }
