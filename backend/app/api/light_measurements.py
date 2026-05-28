from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.models import AuthUser
from app.db.session import get_async_session
from app.light_measurements.repository import LightMeasurementRepository
from app.schemas.light_measurements import LightMeasurementCreate, LightMeasurementDto

router = APIRouter(prefix="/light-measurements", tags=["light-measurements"])


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
        raise HTTPException(status_code=404, detail="Planta no encontrada en Mi Jardin.")
    return measurement
