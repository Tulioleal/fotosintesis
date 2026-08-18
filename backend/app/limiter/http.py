"""Auth limiter response contract helpers.

Centralizes the bounded ``429`` retry contract and the neutral storage
failure / rejection responses shared by every enforcement layer so endpoint
handlers never reveal account state, storage details, or limiter keys.
"""

from __future__ import annotations

from fastapi import HTTPException, status

from app.limiter.policy import AdmissionOutcome, LimiterOutcome

RECOVERY_NEUTRAL_MESSAGE = (
    "If an account with that email exists, we will send you instructions to recover access."
)


def raise_limited(category: str, outcome: AdmissionOutcome) -> HTTPException:
    """Raise the bounded ``429`` retry contract for a rejected request."""
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=f"Too many requests for {category}",
        headers={"Retry-After": str(outcome.retry_after_seconds)},
    )


def raise_recovery_limited(outcome: AdmissionOutcome) -> HTTPException:
    """Raise the neutral recovery ``429`` retry contract.

    The body preserves the endpoint's neutral message so known and unknown
    accounts remain indistinguishable while retry metadata stays equivalent
    for the same active limit state.
    """
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=RECOVERY_NEUTRAL_MESSAGE,
        headers={"Retry-After": str(outcome.retry_after_seconds)},
    )


def raise_storage_failure(
    outcome: AdmissionOutcome, is_recovery: bool = False
) -> HTTPException:
    """Raise the generic fail-closed storage-failure response.

    The bounded retry delay is the outcome's authoritative value already
    clamped by the validated policy maximum; it is never the old hard-coded
    60 and never zero. Never exposes account existence or storage details.
    """
    retry_after = max(1, outcome.retry_after_seconds)
    detail = RECOVERY_NEUTRAL_MESSAGE if is_recovery else "Temporarily unavailable"
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=detail,
        headers={"Retry-After": str(retry_after)},
    )


def enforce_outcome(
    outcome: AdmissionOutcome,
    *,
    category: str,
    recovery: bool = False,
) -> None:
    """Translate an admission outcome into the appropriate HTTP rejection.

    Storage-failure outcomes always fail closed (or use the explicitly
    bounded local fallback decided by the limiter service); rejected
    outcomes use the bounded retry contract.
    """
    if outcome.outcome == LimiterOutcome.allowed:
        return
    if outcome.storage_failure:
        raise raise_storage_failure(outcome, is_recovery=recovery)
    if recovery:
        raise raise_recovery_limited(outcome)
    raise raise_limited(category, outcome)


__all__ = [
    "RECOVERY_NEUTRAL_MESSAGE",
    "enforce_outcome",
    "raise_limited",
    "raise_recovery_limited",
    "raise_storage_failure",
]
