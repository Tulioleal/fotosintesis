from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.assistant.schemas import AssistantChatRequest, AssistantChatResponse
from app.assistant.service import AssistantService
from app.auth.dependencies import get_current_user
from app.auth.models import AuthUser
from app.db.session import get_async_session

router = APIRouter(prefix="/assistant", tags=["assistant"])


@router.post("/chat", response_model=AssistantChatResponse)
async def assistant_chat(
    payload: AssistantChatRequest,
    user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> AssistantChatResponse:
    return await AssistantService(session).chat(user_id=user.id, payload=payload)
