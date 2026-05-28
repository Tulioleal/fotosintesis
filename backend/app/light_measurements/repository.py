from uuid import UUID, uuid4

from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.tables import garden_plants, light_measurements
from app.schemas.light_measurements import LightMeasurementCreate, LightMeasurementDto


class LightMeasurementRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_measurement(
        self, *, user_id: UUID, payload: LightMeasurementCreate
    ) -> LightMeasurementDto | None:
        if payload.garden_plant_id and not await self._plant_exists(
            user_id=user_id, garden_plant_id=payload.garden_plant_id
        ):
            return None

        measurement_id = uuid4()
        await self.session.execute(
            insert(light_measurements).values(
                id=measurement_id,
                user_id=user_id,
                garden_plant_id=payload.garden_plant_id,
                classification=payload.classification.value,
                lux=payload.lux,
                reliability=payload.reliability.value,
                source=payload.source.value,
                metadata=payload.metadata,
            )
        )
        await self.session.commit()
        return await self.get_measurement(user_id=user_id, measurement_id=measurement_id)

    async def get_measurement(
        self, *, user_id: UUID, measurement_id: UUID
    ) -> LightMeasurementDto | None:
        row = (
            await self.session.execute(
                select(light_measurements).where(
                    light_measurements.c.id == measurement_id,
                    light_measurements.c.user_id == user_id,
                )
            )
        ).first()
        return _measurement_from_row(row._mapping) if row else None

    async def _plant_exists(self, *, user_id: UUID, garden_plant_id: UUID) -> bool:
        row = (
            await self.session.execute(
                select(garden_plants.c.id).where(
                    garden_plants.c.id == garden_plant_id,
                    garden_plants.c.user_id == user_id,
                )
            )
        ).first()
        return row is not None


def _measurement_from_row(row) -> LightMeasurementDto:
    return LightMeasurementDto(
        id=row[light_measurements.c.id],
        user_id=row[light_measurements.c.user_id],
        garden_plant_id=row[light_measurements.c.garden_plant_id],
        classification=row[light_measurements.c.classification],
        lux=row[light_measurements.c.lux],
        reliability=row[light_measurements.c.reliability],
        source=row[light_measurements.c.source],
        metadata=row[light_measurements.c.metadata],
        measured_at=row[light_measurements.c.measured_at],
    )
