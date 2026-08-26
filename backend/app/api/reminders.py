from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.models import AuthUser
from app.db.session import get_async_session
from app.reminders.repository import (
    MissingTimezoneError,
    ReminderRepository,
)
from app.reminders.suggestions import (
    PlantNotFoundError,
    ProviderFailureError,
    ReminderSuggestionService,
)
from app.schemas.reminders import (
    ReminderCreate,
    ReminderDeleteResponse,
    ReminderDto,
    ReminderSuggestionMetricRequest,
    ReminderSuggestionOutcome,
    ReminderSuggestionRequest,
    ReminderUpdate,
)
from app.observability.metrics import metrics_registry
from app.reminders.validation import (
    MissingReminderTimezoneError,
    ReminderValidationError,
    ensure_future_due,
    resolve_effective_timezone,
)
from app.scheduling.timezone import (
    InvalidTimezoneError,
    NonexistentLocalTimeError,
)

router = APIRouter(prefix="/reminders", tags=["reminders"])


def _scheduling_error(status_code: int, error: Exception) -> HTTPException:
    return HTTPException(status_code=status_code, detail=str(error))


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
    try:
        _ensure_future_due(payload, user)
        reminder = await ReminderRepository(session).create_reminder(
            user_id=user.id, payload=payload
        )
    except MissingTimezoneError as error:
        raise _scheduling_error(422, error)
    except NonexistentLocalTimeError as error:
        raise _scheduling_error(422, error)
    except InvalidTimezoneError as error:
        raise _scheduling_error(422, error)
    if reminder is None:
        raise HTTPException(status_code=404, detail="Plant not found in My Garden.")
    return reminder


@router.post("/suggestions", response_model=ReminderSuggestionOutcome)
async def suggest_reminder(
    payload: ReminderSuggestionRequest,
    user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> ReminderSuggestionOutcome:
    try:
        return await ReminderSuggestionService(session).suggest(
            user_id=user.id, payload=payload
        )
    except PlantNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error))
    except ProviderFailureError as error:
        raise HTTPException(status_code=503, detail=str(error))


@router.post("/suggestions/metrics", response_model=dict[str, str])
async def record_suggestion_metric(
    payload: ReminderSuggestionMetricRequest,
    user: AuthUser = Depends(get_current_user),
) -> dict[str, str]:
    metrics_registry.record_reminder_suggestion_outcome(outcome=payload.outcome)
    return {"status": "recorded"}


@router.patch("/{reminder_id}", response_model=ReminderDto)
async def update_reminder(
    reminder_id: UUID,
    payload: ReminderUpdate,
    user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> ReminderDto:
    try:
        if payload.date is not None or payload.time is not None:
            _ensure_future_due(payload, user)
        reminder = await ReminderRepository(session).update_reminder(
            user_id=user.id, reminder_id=reminder_id, payload=payload
        )
    except MissingTimezoneError as error:
        raise _scheduling_error(422, error)
    except NonexistentLocalTimeError as error:
        raise _scheduling_error(422, error)
    except InvalidTimezoneError as error:
        raise _scheduling_error(422, error)
    if reminder is None:
        raise HTTPException(status_code=404, detail="Reminder not found.")
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
        raise HTTPException(status_code=404, detail="Reminder not found.")
    return reminder


@router.delete("/{reminder_id}", response_model=ReminderDeleteResponse)
async def delete_reminder(
    reminder_id: UUID,
    user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> ReminderDeleteResponse:
    deleted = await ReminderRepository(session).delete_reminder(user_id=user.id, reminder_id=reminder_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Reminder not found.")
    return ReminderDeleteResponse(status="deleted")


def _ensure_future_due(payload: ReminderCreate | ReminderUpdate, user: AuthUser) -> None:
    if payload.date is None or payload.time is None:
        return
    try:
        zone = resolve_effective_timezone(
            override=payload.timezone, user_timezone=user.timezone
        )
    except MissingReminderTimezoneError as error:
        raise MissingTimezoneError(str(error)) from None
    try:
        ensure_future_due(due_date=payload.date, due_time=payload.time, zone=zone)
    except ReminderValidationError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
