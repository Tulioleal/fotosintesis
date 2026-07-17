from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import and_, desc, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.tables import (
    conversation_messages,
    conversations,
    garden_plants,
    light_measurements,
    plant_profiles,
    reminders,
)
from app.db.repository import RepositoryBase


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
                select(garden_plants, plant_profiles)
                .join(plant_profiles, plant_profiles.c.id == garden_plants.c.profile_id)
                .where(garden_plants.c.user_id == user_id)
                .order_by(desc(garden_plants.c.created_at))
            )
        ).all()
        return [
            {
                "id": row._mapping[garden_plants.c.id],
                "nickname": row._mapping[garden_plants.c.nickname],
                "location": row._mapping[garden_plants.c.location],
                "scientific_name": row._mapping[plant_profiles.c.scientific_name],
                "common_name": row._mapping[plant_profiles.c.common_name],
            }
            for row in rows
        ]

    async def create_reminder(
        self,
        *,
        user_id: UUID,
        garden_plant_id: UUID,
        action: str,
        due_at: datetime,
        recurrence: str | None,
        justification: str | None,
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
        await self.session.execute(
            insert(reminders).values(
                id=reminder_id,
                user_id=user_id,
                garden_plant_id=garden_plant_id,
                action=action,
                due_at=due_at,
                recurrence=recurrence,
                suggestion_justification=justification,
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
