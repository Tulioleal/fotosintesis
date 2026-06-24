from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.models import AuthUser
from app.db.session import get_async_session
from app.identification.gbif import GbifClient
from app.identification.repository import IdentificationRepository
from app.identification.schemas import ConfirmationResponse, IdentificationResponse
from app.providers.factory import get_provider_registry
from app.storage.factory import get_object_storage
from app.storage.models import ObjectUpload

router = APIRouter(prefix="/identifications", tags=["identifications"])

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_IMAGE_BYTES = 8 * 1024 * 1024


@router.post("", response_model=IdentificationResponse, status_code=status.HTTP_201_CREATED)
async def create_identification(
    file: Annotated[UploadFile, File(description="Plant image to identify")],
    user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> IdentificationResponse:
    content = await file.read()
    mime_type = file.content_type or "application/octet-stream"
    if mime_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=415, detail="Upload a JPEG, PNG, or WebP image.")
    if not content or len(content) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=422, detail="The image is empty or exceeds 8 MB.")

    extension = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}[mime_type]
    path = f"identifications/{user.id}/{uuid4()}.{extension}"
    stored = await get_object_storage().put_object(
        ObjectUpload(path=path, content=content, mime_type=mime_type)
    )

    repository = IdentificationRepository(session)
    identification_id = await repository.create_identification(
        user_id=user.id,
        storage_path=stored.path,
        mime_type=stored.mime_type,
        size_bytes=stored.size_bytes,
        metadata={"filename": file.filename or "plant-image", "bucket": stored.bucket},
        status="needs_confirmation",
        message="Review these possible matches before confirming a species.",
    )

    try:
        analysis = await get_provider_registry().vision.analyze_image(
            content,
            prompt=(
                "Identify visible plant candidates only. Return common name, scientific name, "
                "visible traits and qualitative confidence; never present the result as definitive."
            ),
            mime_type=mime_type,
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
        if taxonomy.matched:
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
    candidate = await IdentificationRepository(session).confirm_candidate(
        identification_id=identification_id, candidate_id=candidate_id, user_id=user.id
    )
    if candidate is None:
        raise HTTPException(
            status_code=409,
            detail="You can only confirm a taxonomically validated candidate.",
        )
    return ConfirmationResponse(status="confirmed", candidate=candidate)
