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
            HomeAccessItem(key="identify", label="Identificar planta", href="/identify"),
            HomeAccessItem(key="search", label="Buscar plantas", href="/search"),
            HomeAccessItem(key="light_meter", label="Medidor de luz", href="/light-meter"),
            HomeAccessItem(key="reminders", label="Recordatorios", href="/reminders"),
            HomeAccessItem(key="garden", label="Mi Jardín", href="/garden"),
            HomeAccessItem(key="assistant", label="Asistente", href="/assistant"),
        ],
    )
