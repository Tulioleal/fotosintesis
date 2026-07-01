from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.models import AuthUser
from app.db.session import get_async_session
from app.light_measurements.repository import LightMeasurementRepository
from app.schemas.light_measurements import LightMeasurementCreate, LightMeasurementDto

router = APIRouter(prefix="/light-measurements", tags=["light-measurements"])


@router.get("", response_model=list[LightMeasurementDto])
async def list_light_measurements(
    garden_plant_id: UUID | None = Query(default=None),
    limit: int = Query(default=5, ge=1, le=20),
    user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> list[LightMeasurementDto]:
    return await LightMeasurementRepository(session).list_measurements(
        user_id=user.id,
        garden_plant_id=garden_plant_id,
        limit=limit,
    )


@router.post("", response_model=LightMeasurementDto, status_code=status.HTTP_201_CREATED)
async def create_light_measurement(
    payload: LightMeasurementCreate,
    user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> LightMeasurementDto:
    measurement = await LightMeasurementRepository(session).create_measurement(
        user_id=user.id, payload=payload
    )
    if measurement is None:
        raise HTTPException(status_code=404, detail="Plant not found in My Garden.")
    return measurement
