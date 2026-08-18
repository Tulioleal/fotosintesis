"""Limiter service orchestrating policy, keyed digests, and shared state.

The service is the single enforcement boundary used by backend endpoints. It
derives opaque keyed digests from normalized identifiers, evaluates every
applicable rule in one atomic operation, applies the configured storage
failure mode, and records only closed-category/outcome metrics.
"""

from __future__ import annotations

from app.core.settings import get_settings
from app.limiter.hashing import KeyedDigest
from app.limiter.policy import (
    AdmissionOutcome,
    Dimension,
    EndpointCategory,
    LimiterOutcome,
    LimiterPolicy,
)
from app.limiter.repository import LimiterRepository
from app.observability.metrics import metrics_registry


def _normalize_account(email: str) -> str:
    return email.strip().lower()


class LimiterService:
    """Enforce distributed authentication limits for one request boundary."""

    def __init__(
        self,
        repository: LimiterRepository,
        *,
        policy: LimiterPolicy | None = None,
        digest: KeyedDigest | None = None,
        enabled: bool | None = None,
    ) -> None:
        settings = get_settings()
        self.repository = repository
        self.policy = policy if policy is not None else settings.limiter_policy()
        self.digest = digest if digest is not None else (
            KeyedDigest(
                secret=settings.auth_limiter_hmac_secret or "",
                key_version=self.policy.hmac_key_version,
            )
        )
        self.enabled = enabled if enabled is not None else settings.auth_limiter_enabled

    def _keys_for(
        self,
        *,
        category: EndpointCategory,
        source_identifier: str | None,
        account_identifier: str | None,
    ) -> dict[Dimension, str]:
        keys: dict[Dimension, str] = {}
        endpoint = self.policy.endpoints[category]
        if source_identifier:
            keys[Dimension.source] = self.digest.derive(
                dimension=Dimension.source, identifier=source_identifier
            )
        if account_identifier and endpoint.account is not None:
            keys[Dimension.account] = self.digest.derive(
                dimension=Dimension.account,
                identifier=_normalize_account(account_identifier),
            )
        return keys

    async def admit(
        self,
        *,
        category: EndpointCategory,
        source_identifier: str | None,
        account_identifier: str | None = None,
    ) -> AdmissionOutcome:
        """Evaluate every applicable rule before authentication work.

        A missing trusted source uses the conservative missing-source policy:
        the request is rejected without consuming any source rule.
        """
        if not self.enabled:
            return AdmissionOutcome(outcome=LimiterOutcome.allowed)

        keys = self._keys_for(
            category=category,
            source_identifier=source_identifier,
            account_identifier=account_identifier,
        )
        if Dimension.source not in keys:
            metrics_registry.record_limiter_outcome(
                category=category, outcome=LimiterOutcome.rejected
            )
            return AdmissionOutcome(
                outcome=LimiterOutcome.rejected,
                retry_after_seconds=self.policy.retry_after_for_category(category),
            )

        try:
            result = await self.repository.admit(
                category=category, keys=keys, policy=self.policy
            )
        except Exception:
            # Storage failure policy: always fail closed. A limiter-storage
            # exception must never admit authentication work.
            metrics_registry.record_limiter_outcome(
                category=category, outcome=LimiterOutcome.storage_failure
            )
            return AdmissionOutcome(
                outcome=LimiterOutcome.rejected,
                retry_after_seconds=self.policy.retry_after_for_category(category),
                storage_failure=True,
            )
        metrics_registry.record_limiter_outcome(category=category, outcome=result.outcome)
        return result

    async def relax_account(
        self,
        *,
        category: EndpointCategory,
        account_identifier: str,
    ) -> None:
        if not self.enabled:
            return
        account_key = self.digest.derive(
            dimension=Dimension.account,
            identifier=_normalize_account(account_identifier),
        )
        await self.repository.relax_account(category=category, account_key=account_key)

    async def cleanup(self, *, batch_size: int | None = None) -> int:
        if not self.enabled:
            return 0
        settings = get_settings()
        size = batch_size or settings.auth_limiter_cleanup_batch_size
        return await self.repository.cleanup(
            batch_size=size, retention_seconds=self.policy.retention_seconds
        )


__all__ = ["LimiterService"]
