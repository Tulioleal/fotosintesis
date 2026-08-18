"""Limiter interface shared by enforcement layers.

The interface is deliberately identifier-free: callers pass dimension keys
that are already opaque keyed digests, so raw accounts and source addresses
never reach the enforcement boundary.
"""

from __future__ import annotations

from typing import Protocol

from app.limiter.policy import (
    AdmissionOutcome,
    Dimension,
    EndpointCategory,
)


class Limiter(Protocol):
    """Evaluate and relax shared authentication abuse limits."""

    async def admit(
        self,
        *,
        category: EndpointCategory,
        keys: dict[Dimension, str],
    ) -> AdmissionOutcome:
        """Admit a request by atomically consuming every applicable rule.

        ``keys`` maps each applicable :class:`Dimension` to an already-keyed
        opaque digest. The request is admitted only when every rule admits it;
        otherwise all consumption is rolled back and a bounded rejection is
        returned.
        """
        ...

    async def relax(
        self,
        *,
        category: EndpointCategory,
        account_key: str,
    ) -> None:
        """Relax only the account-specific state for ``category``.

        This must never clear source-wide or unrelated limits.
        """
        ...

    async def cleanup(self, *, batch_size: int) -> int:
        """Remove expired limiter windows in bounded batches.

        Returns the number of removed rows.
        """
        ...


__all__ = ["Limiter"]
