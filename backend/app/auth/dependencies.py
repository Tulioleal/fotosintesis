from datetime import timedelta

from fastapi import Cookie, Header, HTTPException, Response, status

from app.auth.models import AuthSession, AuthUser
from app.auth.repository import auth_repository
from app.core.settings import get_settings


def _idle_ttl() -> timedelta:
    return timedelta(minutes=get_settings().session_idle_ttl_minutes)


def absolute_ttl() -> timedelta:
    return timedelta(days=get_settings().session_absolute_ttl_days)


def set_session_cookie(response: Response, session: AuthSession) -> None:
    settings = get_settings()
    response.set_cookie(
        key=settings.session_cookie_name,
        value=session.token,
        httponly=True,
        secure=settings.environment != "local",
        samesite="lax",
        expires=session.expires_at,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(key=get_settings().session_cookie_name, path="/")


async def get_current_user(
    response: Response,
    fotosintesis_session: str | None = Cookie(default=None, alias="fotosintesis_session"),
    authorization: str | None = Header(default=None),
) -> AuthUser:
    if not fotosintesis_session and authorization and authorization.startswith("Bearer "):
        fotosintesis_session = authorization.removeprefix("Bearer ").strip()
    if not fotosintesis_session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    resolved = auth_repository.get_valid_session(fotosintesis_session, _idle_ttl())
    if resolved is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    session, user = resolved
    set_session_cookie(response, session)
    return user


async def get_current_session(
    response: Response,
    fotosintesis_session: str | None = Cookie(default=None, alias="fotosintesis_session"),
    authorization: str | None = Header(default=None),
) -> tuple[AuthSession, AuthUser]:
    if not fotosintesis_session and authorization and authorization.startswith("Bearer "):
        fotosintesis_session = authorization.removeprefix("Bearer ").strip()
    if not fotosintesis_session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    resolved = auth_repository.get_valid_session(fotosintesis_session, _idle_ttl())
    if resolved is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    session, user = resolved
    set_session_cookie(response, session)
    return session, user
