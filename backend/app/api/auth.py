from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.auth.dependencies import absolute_ttl, clear_session_cookie, get_current_session, set_session_cookie
from app.auth.models import AuthUser
from app.auth.repository import DuplicateEmailError, InvalidCredentialsError, auth_repository
from app.auth.schemas import (
    CredentialsVerifyRequest,
    CredentialsVerifyResponse,
    PublicAuthUser,
    RecoveryConfirmRequest,
    RecoveryRequest,
    RecoveryResponse,
    RegisterRequest,
    RegisterResponse,
)
from app.core.settings import get_settings
from app.observability.logging import get_logger

router = APIRouter(prefix="/auth", tags=["auth"])
logger = get_logger(__name__)


def to_public_user(user: AuthUser) -> PublicAuthUser:
    return PublicAuthUser(
        id=user.id,
        name=user.name,
        email=user.email,
        email_verified=user.email_verified,
    )


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest) -> RegisterResponse:
    try:
        user = auth_repository.create_user(payload.name, str(payload.email), payload.password)
    except DuplicateEmailError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered") from error
    return RegisterResponse(user=to_public_user(user))


@router.post("/credentials/verify", response_model=CredentialsVerifyResponse)
async def verify_credentials(payload: CredentialsVerifyRequest, response: Response) -> CredentialsVerifyResponse:
    try:
        user = auth_repository.verify_credentials(str(payload.email), payload.password)
    except InvalidCredentialsError as error:
        logger.info("credential login rejected", extra={"ctx_reason": str(error)})
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials") from error

    settings = get_settings()
    session = auth_repository.create_session(
        user.id,
        idle_ttl=timedelta(minutes=settings.session_idle_ttl_minutes),
        absolute_ttl=absolute_ttl(),
    )
    set_session_cookie(response, session)
    return CredentialsVerifyResponse(
        user=to_public_user(user),
        session_token=session.token,
        session_expires_at=session.expires_at,
    )


@router.post("/logout")
async def logout(response: Response, current: tuple = Depends(get_current_session)) -> dict[str, str]:
    session, _user = current
    auth_repository.invalidate_session(session.token)
    clear_session_cookie(response)
    return {"status": "ok"}


@router.post("/recovery/request", response_model=RecoveryResponse)
async def request_recovery(payload: RecoveryRequest) -> RecoveryResponse:
    settings = get_settings()
    auth_repository.create_recovery_token(
        str(payload.email), ttl=timedelta(minutes=settings.recovery_token_ttl_minutes)
    )
    return RecoveryResponse(
        status="ok",
        message="Si existe una cuenta con ese correo, te enviaremos instrucciones para recuperar el acceso.",
    )


@router.post("/recovery/confirm")
async def confirm_recovery(_payload: RecoveryConfirmRequest) -> dict[str, str]:
    return {"status": "prepared"}
