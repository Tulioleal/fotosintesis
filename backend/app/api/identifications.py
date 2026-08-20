from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.models import AuthUser
from app.core.settings import get_settings
from app.db.session import get_async_session
from app.identification.gbif import GbifClient
from app.identification.confirmation import (
    CandidateConfirmationService,
    ConfirmationRejectedError,
    ConfirmationSchedulingUnavailable,
)
from app.identification.image_processing import (
    ImageValidationError,
    normalize_identification_image,
)
from app.identification.repository import IdentificationRepository
from app.identification.schemas import ConfirmationResponse, IdentificationResponse
from app.enrichment import get_current_enrichment_policy
from app.jobs.repository import JobRepository
from app.jobs.schemas import CandidateEnrichmentStatus
from app.observability.logging import get_logger
from app.providers.factory import get_provider_registry
from app.storage.factory import get_object_storage
from app.storage.models import ObjectUpload

logger = get_logger(__name__)

router = APIRouter(prefix="/identifications", tags=["identifications"])

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}


@router.post("", response_model=IdentificationResponse, status_code=status.HTTP_201_CREATED)
async def create_identification(
    file: Annotated[UploadFile, File(description="Plant image to identify")],
    user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> IdentificationResponse:
    settings = get_settings()
    content = await file.read()
    mime_type = file.content_type or "application/octet-stream"
    if mime_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=415, detail="Upload a JPEG, PNG, or WebP image.")
    if not content or len(content) > settings.identification_max_image_bytes:
        raise HTTPException(
            status_code=422,
            detail=f"The image is empty or exceeds {settings.identification_max_image_bytes} bytes.",
        )

    try:
        normalized = normalize_identification_image(content)
    except ImageValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from None

    path = f"identifications/{user.id}/{uuid4()}.jpg"
    stored = await get_object_storage().put_object(
        ObjectUpload(path=path, content=normalized.content, mime_type=normalized.mime_type)
    )

    repository = IdentificationRepository(session)
    try:
        identification_id = await repository.create_identification(
            user_id=user.id,
            storage_path=stored.path,
            mime_type=stored.mime_type,
            size_bytes=stored.size_bytes,
            metadata={
                "filename": file.filename or "plant-image",
                "bucket": stored.bucket,
                "width": normalized.width,
                "height": normalized.height,
            },
            status="needs_confirmation",
            message="Review these possible matches before confirming a species.",
        )
    except Exception:
        await _compensate_stored_object(stored.path)
        raise

    try:
        analysis = await get_provider_registry().vision.analyze_image(
            normalized.content,
            prompt=(
                "Identify visible plant candidates only. Return common name, scientific name, "
                "visible traits and qualitative confidence; never present the result as definitive."
            ),
            mime_type=normalized.mime_type,
        )
    except Exception:
        return await _sad_response(
            repository,
            identification_id,
            user.id,
            "maas_unavailable",
            "We could not query the visual analysis. Retry or use manual search.",
        )

    candidates = [candidate for candidate in analysis.candidates[:3] if candidate.scientific_name]
    if "blurry" in analysis.description.lower() or analysis.metadata.get("image_quality") == "blurry":
        return await _sad_response(
            repository,
            identification_id,
            user.id,
            "blurry_image",
            "The image appears blurry. Retry with better focus and natural light.",
            candidates=candidates,
        )

    reliable = [c for c in candidates if c.confidence_label.value in {"high", "medium"}]
    if not candidates:
        return await _sad_response(
            repository,
            identification_id,
            user.id,
            "no_plant",
            "We did not find a clear plant in the image. Try a closer photo.",
        )
    if not reliable:
        return await _sad_response(
            repository,
            identification_id,
            user.id,
            "low_confidence",
            "The image did not produce reliable matches. Retry with better light and focus.",
            candidates=candidates,
        )

    gbif = GbifClient()
    validated = 0
    for candidate in reliable:
        taxonomy = await gbif.match_name(candidate.scientific_name)
        if taxonomy.has_canonical_identity:
            validated += 1
        await repository.add_candidate(
            identification_id=identification_id, candidate=candidate, taxonomy=taxonomy
        )

    if validated == 0:
        return await _sad_response(
            repository,
            identification_id,
            user.id,
            "no_gbif_match",
            "We saw possible plants, but GBIF did not validate the suggested names. Use manual search.",
        )

    response = await repository.get_response(identification_id, user.id)
    if response is None:
        raise HTTPException(status_code=404, detail="Identification not found")
    return response


async def _compensate_stored_object(path: str) -> None:
    """Best-effort deletion of a just-stored object whose record could not persist."""
    try:
        await get_object_storage().delete_object(path)
    except Exception:
        logger.exception(
            "identification_object_cleanup_failed",
            extra={"ctx_object_path": path},
        )


async def _sad_response(
    repository: IdentificationRepository,
    identification_id: UUID,
    user_id: UUID,
    sad_path: str,
    message: str,
    candidates: list | None = None,
) -> IdentificationResponse:
    await repository.mark_recoverable(
        identification_id=identification_id,
        status="retry_needed",
        sad_path=sad_path,
        message=message,
    )
    if candidates:
        gbif = GbifClient()
        for candidate in candidates[:3]:
            await repository.add_candidate(
                identification_id=identification_id,
                candidate=candidate,
                taxonomy=await gbif.match_name(candidate.scientific_name),
            )
    response = await repository.get_response(identification_id, user_id)
    if response is None:
        raise HTTPException(status_code=404, detail="Identification not found")
    return response


@router.post("/{identification_id}/candidates/{candidate_id}/confirm", response_model=ConfirmationResponse)
async def confirm_candidate(
    identification_id: UUID,
    candidate_id: UUID,
    user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> ConfirmationResponse:
    try:
        return await CandidateConfirmationService(session).confirm(
            identification_id=identification_id,
            candidate_id=candidate_id,
            user_id=user.id,
        )
    except ConfirmationRejectedError:
        raise HTTPException(
            status_code=409,
            detail="You can only confirm a taxonomically validated candidate.",
        ) from None
    except ConfirmationSchedulingUnavailable:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Plant enrichment scheduling is temporarily unavailable.",
        ) from None


@router.get(
    "/candidates/{candidate_id}/enrichment",
    response_model=CandidateEnrichmentStatus,
)
async def get_candidate_enrichment(
    candidate_id: UUID,
    user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> CandidateEnrichmentStatus:
    enrichment = await JobRepository(session).get_candidate_enrichment_status(
        candidate_id=candidate_id,
        user_id=user.id,
        policy_version=get_current_enrichment_policy().version,
    )
    if enrichment is None:
        raise HTTPException(status_code=404, detail="Candidate enrichment not found.")
    return enrichment
