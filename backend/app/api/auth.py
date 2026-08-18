from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.auth.dependencies import (
    absolute_ttl,
    clear_session_cookie,
    get_auth_repository,
    get_current_session,
    set_session_cookie,
)
from app.auth.models import AuthUser
from app.auth.repository import DatabaseAuthRepository, DuplicateEmailError, InvalidCredentialsError
from app.auth.schemas import (
    CredentialsVerifyRequest,
    CredentialsVerifyResponse,
    PublicAuthUser,
    RateLimitResponse,
    RecoveryConfirmRequest,
    RecoveryRequest,
    RecoveryResponse,
    RegisterRequest,
    RegisterResponse,
)
from app.core.settings import get_settings
from app.limiter.dependencies import get_limiter_service, validate_source_assertion
from app.limiter.http import enforce_outcome
from app.limiter.policy import EndpointCategory
from app.limiter.service import LimiterService
from app.observability.logging import get_logger

router = APIRouter(prefix="/auth", tags=["auth"])
logger = get_logger(__name__)

AuthRepo = Annotated[DatabaseAuthRepository, Depends(get_auth_repository)]
Limiter = Annotated[LimiterService, Depends(get_limiter_service)]
SourceKey = Annotated[str | None, Depends(validate_source_assertion)]


def to_public_user(user: AuthUser) -> PublicAuthUser:
    return PublicAuthUser(
        id=user.id,
        name=user.name,
        email=user.email,
        email_verified=user.email_verified,
    )


RATE_LIMIT_RESPONSES = {
    status.HTTP_429_TOO_MANY_REQUESTS: {
        "model": RateLimitResponse,
        "description": "Distributed authentication limit reached; retry after the bounded delay.",
        "headers": {
            "Retry-After": {
                "description": "Whole-second delay the client should wait before retrying (clamped to the configured maximum).",
                "schema": {"type": "integer", "minimum": 1},
            }
        },
    },
    status.HTTP_503_SERVICE_UNAVAILABLE: {
        "model": RateLimitResponse,
        "description": "Shared limiter storage unavailable; the request is denied without account or storage details.",
        "headers": {
            "Retry-After": {
                "description": "Whole-second delay the client should wait before retrying.",
                "schema": {"type": "integer", "minimum": 1},
            }
        },
    },
}


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    responses=RATE_LIMIT_RESPONSES,
)
async def register(
    payload: RegisterRequest,
    repository: AuthRepo,
    limiter: Limiter,
    source_key: SourceKey,
) -> RegisterResponse:
    outcome = await limiter.admit(
        category=EndpointCategory.registration, source_identifier=source_key
    )
    enforce_outcome(outcome, category="registration")
    try:
        user = await repository.create_user(payload.name, str(payload.email), payload.password)
    except DuplicateEmailError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered") from error
    return RegisterResponse(user=to_public_user(user))


@router.post("/credentials/verify", response_model=CredentialsVerifyResponse, responses=RATE_LIMIT_RESPONSES)
async def verify_credentials(
    payload: CredentialsVerifyRequest,
    response: Response,
    repository: AuthRepo,
    limiter: Limiter,
    source_key: SourceKey,
) -> CredentialsVerifyResponse:
    outcome = await limiter.admit(
        category=EndpointCategory.credential_verification,
        source_identifier=source_key,
        account_identifier=str(payload.email),
    )
    enforce_outcome(outcome, category="credential verification")
    try:
        user = await repository.verify_credentials(str(payload.email), payload.password)
    except InvalidCredentialsError as error:
        logger.info("credential login rejected", extra={"ctx_reason": str(error)})
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials") from error

    await limiter.relax_account(
        category=EndpointCategory.credential_verification,
        account_identifier=str(payload.email),
    )
    settings = get_settings()
    session = await repository.create_session(
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
async def logout(
    response: Response, repository: AuthRepo, current: tuple = Depends(get_current_session)
) -> dict[str, str]:
    session, _user = current
    await repository.invalidate_session(session.token)
    clear_session_cookie(response)
    return {"status": "ok"}


@router.get("/session")
async def validate_session(_current: tuple = Depends(get_current_session)) -> dict[str, str]:
    return {"status": "ok"}


@router.post("/recovery/request", response_model=RecoveryResponse, responses=RATE_LIMIT_RESPONSES)
async def request_recovery(
    payload: RecoveryRequest,
    repository: AuthRepo,
    limiter: Limiter,
    source_key: SourceKey,
) -> RecoveryResponse:
    outcome = await limiter.admit(
        category=EndpointCategory.recovery_initiation,
        source_identifier=source_key,
        account_identifier=str(payload.email),
    )
    enforce_outcome(outcome, category="recovery", recovery=True)
    settings = get_settings()
    await repository.create_recovery_token(
        str(payload.email), ttl=timedelta(minutes=settings.recovery_token_ttl_minutes)
    )
    return RecoveryResponse(
        status="ok",
        message="If an account with that email exists, we will send you instructions to recover access.",
    )


@router.post("/recovery/confirm", responses=RATE_LIMIT_RESPONSES)
async def confirm_recovery(
    payload: RecoveryConfirmRequest,
    limiter: Limiter,
    source_key: SourceKey,
) -> dict[str, str]:
    # The account dimension is derived from the submitted token through the
    # existing keyed digest path: only an opaque keyed digest is ever persisted
    # or observed, never the raw token. Schema-invalid payloads are rejected by
    # deterministic FastAPI validation (422) before this endpoint runs.
    # Token-shaped requests that reach token-state handling stay neutral
    # regarding token existence, expiration, or use, and rotating source
    # addresses cannot bypass the token-derived account bound. Volumetric
    # malformed traffic remains an ingress/edge concern, not an application
    # limit.
    outcome = await limiter.admit(
        category=EndpointCategory.recovery_confirmation,
        source_identifier=source_key,
        account_identifier=str(payload.token),
    )
    enforce_outcome(outcome, category="recovery confirmation", recovery=True)
    return {"status": "prepared"}


@router.post("/admit/authjs_post", responses=RATE_LIMIT_RESPONSES)
async def admit_authjs_post(
    limiter: Limiter,
    source_key: SourceKey,
) -> dict[str, str]:
    """Narrow internal admission endpoint for relevant unauthenticated Auth.js POST operations.

    The frontend Auth.js boundary calls this endpoint (protected by the same
    signed source assertion used by every other limiter header) before
    invoking Auth.js work. A rejected or storage-failed outcome is translated
    into the bounded retry contract so the distributed ``authjs_post`` policy
    has a real runtime call site and session reads and authenticated logout
    remain unchanged.
    """
    outcome = await limiter.admit(
        category=EndpointCategory.authjs_post, source_identifier=source_key
    )
    enforce_outcome(outcome, category="authjs_post")
    return {"status": "ok"}
