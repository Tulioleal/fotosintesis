from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import to_public_user
from app.auth.dependencies import get_current_user
from app.auth.models import AuthUser
from app.auth.schemas import HomeAccessItem, HomeSummaryResponse
from app.db.session import get_async_session
from app.profile_garden.repository import PlantProfileGardenRepository

router = APIRouter(prefix="/home", tags=["home"])


@router.get("/summary", response_model=HomeSummaryResponse)
async def home_summary(
    user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> HomeSummaryResponse:
    repository = PlantProfileGardenRepository(session)
    garden_count = await repository.count_garden_plants(user_id=user.id)
    recent_garden_plants = await repository.list_recent_garden_plants(
        user_id=user.id, limit=8
    )
    return HomeSummaryResponse(
        user=to_public_user(user),
        empty_state=garden_count == 0,
        access=[
            HomeAccessItem(key="identify", label="Identify plant", href="/identify"),
            HomeAccessItem(key="search", label="Search plants", href="/search"),
            HomeAccessItem(key="light_meter", label="Light meter", href="/light-meter"),
            HomeAccessItem(key="reminders", label="Reminders", href="/reminders"),
            HomeAccessItem(key="garden", label="My Garden", href="/garden"),
            HomeAccessItem(key="assistant", label="Assistant", href="/assistant"),
        ],
        garden_count=garden_count,
        recent_garden_plants=recent_garden_plants,
    )
