"""FastAPI dependencies wiring the limiter and trusted source assertion.

The backend never trusts arbitrary forwarding headers or client-supplied
source keys. Source identity arrives only as an opaque key plus an HMAC
assertion produced by the frontend trust boundary with a dedicated shared
secret; a missing or invalid assertion falls back to the conservative
missing-source policy.
"""

from __future__ import annotations

import hashlib
import hmac

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import get_settings
from app.db.session import get_async_session
from app.limiter.policy import (
    LIMITER_HEADER_SOURCE_ASSERTION,
    LIMITER_HEADER_SOURCE_KEY,
)
from app.limiter.repository import LimiterRepository
from app.limiter.service import LimiterService


def _constant_time_equal(left: str, right: str) -> bool:
    return hmac.compare_digest(left.encode("utf-8"), right.encode("utf-8"))


def validate_source_assertion(
    source_key: str | None = Header(default=None, alias=LIMITER_HEADER_SOURCE_KEY),
    source_assertion: str | None = Header(default=None, alias=LIMITER_HEADER_SOURCE_ASSERTION),
) -> str | None:
    """Return the trusted opaque source key, or ``None`` for the missing-source policy.

    The assertion is an HMAC over the opaque source key produced with the
    internal assertion secret shared with the frontend boundary. A request
    that lacks either header, or whose assertion does not verify, is treated
    as having no trusted source identity.
    """
    secret = get_settings().auth_limiter_assertion_secret
    if not secret:
        return None
    if not source_key or not source_assertion:
        return None
    expected = hmac.new(
        secret.encode("utf-8"), source_key.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    if not _constant_time_equal(expected, source_assertion):
        return None
    return source_key


async def get_limiter_service(
    session: AsyncSession = Depends(get_async_session),
) -> LimiterService:
    return LimiterService(repository=LimiterRepository(session))


__all__ = ["get_limiter_service", "validate_source_assertion"]
