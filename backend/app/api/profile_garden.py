from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.models import AuthUser
from app.db.session import get_async_session
from app.enrichment import get_current_enrichment_policy
from app.jobs.repository import JobRepository
from app.observability.logging import get_logger
from app.profile_garden.repository import (
    GardenImageValidationError,
    PlantProfileGardenRepository,
    canonical_identity_fields,
)
from app.profile_garden.schemas import (
    GardenDeleteResponse,
    GardenPlantCreate,
    GardenPlantResponse,
    PlantProfileResponse,
)
from app.storage.base import ObjectNotFoundError
from app.storage.factory import get_object_storage

logger = get_logger(__name__)

router = APIRouter(tags=["plant-profile-garden"])


@router.get("/plant-profiles/{scientific_name}", response_model=PlantProfileResponse)
async def get_plant_profile(
    scientific_name: str,
    candidate_id: Annotated[UUID, Query(alias="candidateId")],
    region: Annotated[str | None, Query()] = None,
    country: Annotated[str | None, Query()] = None,
    language: Annotated[str | None, Query()] = None,
    user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> PlantProfileResponse:
    repository = PlantProfileGardenRepository(session)
    candidate = await repository.confirmed_candidate(candidate_id, user.id)
    if candidate is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You can only view profiles of confirmed and validated plants.",
        )

    candidate_name = candidate.accepted_scientific_name or candidate.suggested_scientific_name
    if candidate_name.strip().casefold() != scientific_name.strip().casefold():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The confirmed candidate does not match the requested profile.",
        )

    profile = await repository.get_or_create_profile(
        scientific_name=candidate_name,
        common_name=candidate.common_name,
        region=region,
        country=country,
        language=language,
        **canonical_identity_fields(candidate),
    )
    enrichment = await JobRepository(session).get_candidate_enrichment_status(
        candidate_id=candidate_id,
        user_id=user.id,
        policy_version=get_current_enrichment_policy().version,
    )
    return profile.model_copy(
        update={
            "enrichment": enrichment,
            "confirmed_candidate_image_path": candidate.image_path,
        }
    )


@router.post("/garden", response_model=GardenPlantResponse, status_code=status.HTTP_201_CREATED)
async def save_garden_plant(
    payload: GardenPlantCreate,
    user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> GardenPlantResponse:
    try:
        plant = await PlantProfileGardenRepository(session).save_garden_plant(
            user_id=user.id, payload=payload
        )
    except GardenImageValidationError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    if plant is None:
        raise HTTPException(
            status_code=409,
            detail="You can only save confirmed and validated plants.",
        )
    return plant


@router.get("/garden", response_model=list[GardenPlantResponse])
async def list_garden_plants(
    q: Annotated[str | None, Query()] = None,
    user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> list[GardenPlantResponse]:
    return await PlantProfileGardenRepository(session).list_garden_plants(user_id=user.id, query=q)


@router.get("/garden/{garden_id}", response_model=GardenPlantResponse)
async def get_garden_plant(
    garden_id: UUID,
    user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> GardenPlantResponse:
    plant = await PlantProfileGardenRepository(session).get_garden_plant(garden_id, user.id)
    if plant is None:
        raise HTTPException(status_code=404, detail="Plant not found in My Garden.")
    return plant


@router.get("/garden/{garden_id}/image", response_class=Response)
async def get_garden_plant_image(
    garden_id: UUID,
    user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> Response:
    repository = PlantProfileGardenRepository(session)
    storage_path = await repository.garden_plant_image_path(user_id=user.id, plant_id=garden_id)
    if not storage_path:
        raise HTTPException(status_code=404, detail="Image not found.")
    try:
        content = await get_object_storage().get_object(storage_path)
    except ObjectNotFoundError:
        logger.warning(
            "garden_plant_image_missing",
            extra={"ctx_user_id": str(user.id), "ctx_object_path": storage_path},
        )
        raise HTTPException(status_code=404, detail="Image not found.") from None
    return Response(
        content=content.content,
        media_type=content.mime_type,
        headers={"Cache-Control": "private, no-store"},
    )


@router.delete("/garden/{garden_id}", response_model=GardenDeleteResponse)
async def delete_garden_plant(
    garden_id: UUID,
    confirm_reminders: Annotated[bool, Query()] = False,
    user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> GardenDeleteResponse:
    result = await PlantProfileGardenRepository(session).delete_garden_plant(
        garden_id=garden_id,
        user_id=user.id,
        confirm_reminders=confirm_reminders,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Plant not found in My Garden.")
    if result == "reminder_confirmation_required":
        raise HTTPException(
            status_code=409,
            detail=(
                "This plant has active reminders. "
                "Explicitly confirm to delete it."
            ),
        )
    return GardenDeleteResponse(status=result)
