from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.models import AuthUser
from app.db.session import get_async_session
from app.reminders.repository import ReminderRepository
from app.schemas.reminders import ReminderCreate, ReminderDeleteResponse, ReminderDto, ReminderUpdate

router = APIRouter(prefix="/reminders", tags=["reminders"])


@router.get("", response_model=list[ReminderDto])
async def list_reminders(
    garden_plant_id: Annotated[UUID | None, Query()] = None,
    user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> list[ReminderDto]:
    return await ReminderRepository(session).list_reminders(
        user_id=user.id, garden_plant_id=garden_plant_id
    )


@router.post("", response_model=ReminderDto, status_code=status.HTTP_201_CREATED)
async def create_reminder(
    payload: ReminderCreate,
    user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> ReminderDto:
    _ensure_future_due(payload)
    reminder = await ReminderRepository(session).create_reminder(user_id=user.id, payload=payload)
    if reminder is None:
        raise HTTPException(status_code=404, detail="Planta no encontrada en Mi Jardin.")
    return reminder


@router.patch("/{reminder_id}", response_model=ReminderDto)
async def update_reminder(
    reminder_id: UUID,
    payload: ReminderUpdate,
    user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> ReminderDto:
    if payload.date is not None or payload.time is not None:
        _ensure_future_due(payload)
    reminder = await ReminderRepository(session).update_reminder(
        user_id=user.id, reminder_id=reminder_id, payload=payload
    )
    if reminder is None:
        raise HTTPException(status_code=404, detail="Recordatorio no encontrado.")
    return reminder


@router.post("/{reminder_id}/complete", response_model=ReminderDto)
async def complete_reminder(
    reminder_id: UUID,
    user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> ReminderDto:
    reminder = await ReminderRepository(session).complete_reminder(
        user_id=user.id, reminder_id=reminder_id
    )
    if reminder is None:
        raise HTTPException(status_code=404, detail="Recordatorio no encontrado.")
    return reminder


@router.delete("/{reminder_id}", response_model=ReminderDeleteResponse)
async def delete_reminder(
    reminder_id: UUID,
    user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> ReminderDeleteResponse:
    deleted = await ReminderRepository(session).delete_reminder(user_id=user.id, reminder_id=reminder_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Recordatorio no encontrado.")
    return ReminderDeleteResponse(status="deleted")


def _ensure_future_due(payload: ReminderCreate | ReminderUpdate) -> None:
    if payload.date is None or payload.time is None:
        return
    due_at = datetime.combine(payload.date, payload.time, tzinfo=timezone.utc)
    if due_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=422, detail="La fecha y hora deben ser futuras.")
