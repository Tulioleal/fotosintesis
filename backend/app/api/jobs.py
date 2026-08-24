from datetime import timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.models import AuthUser
from app.core.settings import get_settings
from app.db.session import get_async_session
from app.jobs.repository import JobRepository
from app.jobs.schemas import (
    EnrichmentActivityResponse,
    JobStatusResponse,
    decode_enrichment_activity_cursor,
    encode_enrichment_activity_cursor,
)

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get(
    "/enrichment-activity",
    response_model=EnrichmentActivityResponse,
    responses={
        401: {"description": "Authentication required"},
        422: {"description": "Malformed cursor"},
    },
)
async def get_enrichment_activity(
    response: Response,
    limit: int | None = Query(default=None, ge=1, le=100),
    cursor: str | None = Query(default=None, max_length=512),
    user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> EnrichmentActivityResponse:
    # Owner-scoped, per-user data must never be stored by shared caches.
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["Pragma"] = "no-cache"
    settings = get_settings()
    resolved_limit = min(
        limit or settings.enrichment_activity_max_items,
        settings.enrichment_activity_max_items,
    )
    decoded_cursor = None
    if cursor is not None:
        decoded_cursor = decode_enrichment_activity_cursor(cursor)
        if decoded_cursor is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Invalid activity cursor",
            )
    items, has_more = await JobRepository(session).get_enrichment_activity(
        user_id=user.id,
        limit=resolved_limit,
        terminal_retention_window=timedelta(
            hours=settings.enrichment_activity_terminal_retention_hours
        ),
        cursor=decoded_cursor,
    )
    next_cursor = (
        encode_enrichment_activity_cursor(items[-1])
        if has_more and items
        else None
    )
    return EnrichmentActivityResponse(
        items=items,
        has_more=has_more,
        next_cursor=next_cursor,
    )


@router.get(
    "/{job_id}",
    response_model=JobStatusResponse,
    responses={
        401: {"description": "Authentication required"},
        404: {"description": "Job not found"},
    },
)
async def get_job_status(
    job_id: UUID,
    user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> JobStatusResponse:
    repo = JobRepository(session)
    result = await repo.get_job_status(job_id=job_id, user_id=user.id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return result
