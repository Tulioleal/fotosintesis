from fastapi import APIRouter, Depends

from app.api.auth import to_public_user
from app.auth.dependencies import get_current_user
from app.auth.models import AuthUser
from app.auth.schemas import HomeAccessItem, HomeSummaryResponse

router = APIRouter(prefix="/home", tags=["home"])


@router.get("/summary", response_model=HomeSummaryResponse)
async def home_summary(user: AuthUser = Depends(get_current_user)) -> HomeSummaryResponse:
    return HomeSummaryResponse(
        user=to_public_user(user),
        empty_state=True,
        access=[
            HomeAccessItem(key="identify", label="Identify plant", href="/identify"),
            HomeAccessItem(key="search", label="Search plants", href="/search"),
            HomeAccessItem(key="light_meter", label="Light meter", href="/light-meter"),
            HomeAccessItem(key="reminders", label="Reminders", href="/reminders"),
            HomeAccessItem(key="garden", label="My Garden", href="/garden"),
            HomeAccessItem(key="assistant", label="Assistant", href="/assistant"),
        ],
    )
