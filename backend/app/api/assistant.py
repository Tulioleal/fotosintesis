from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.assistant.schemas import AssistantChatRequest, AssistantChatResponse, AssistantRetryableError
from app.assistant.service import AssistantService
from app.auth.dependencies import get_current_user
from app.auth.models import AuthUser
from app.core.settings import get_settings
from app.db.session import get_async_session

router = APIRouter(prefix="/assistant", tags=["assistant"])


@router.post("/chat", response_model=AssistantChatResponse | AssistantRetryableError)
async def assistant_chat(
    payload: AssistantChatRequest,
    user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> AssistantChatResponse | AssistantRetryableError:
    return await AssistantService(session).chat(user_id=user.id, payload=payload)


@router.post("/chat/stream", response_class=StreamingResponse)
async def assistant_chat_stream(
    payload: AssistantChatRequest,
    user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> StreamingResponse:
    if not get_settings().assistant_progress_streaming_enabled:
        raise HTTPException(status_code=404, detail="Not found")
    service = AssistantService(session)
    return StreamingResponse(
        service.chat_stream(user_id=user.id, payload=payload),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "private, no-store",
            "X-Accel-Buffering": "no",
        },
    )
