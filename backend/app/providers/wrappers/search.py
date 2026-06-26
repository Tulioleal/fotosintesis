"""Fallback wrapper for the search capability."""

from __future__ import annotations

from typing import Any

from app.providers.interfaces import SearchProvider
from app.providers.types import SearchResult
from app.providers.wrappers.exceptions import _UnusableSearchOutputError
from app.providers.wrappers.runner import run_provider_chain


def _search_unusable_hook(
    result: Any, provider_name: str, index: int
) -> _UnusableSearchOutputError | None:
    if not result:
        return _UnusableSearchOutputError(
            f"{provider_name} returned no results"
        )
    return None


class SearchProviderFallbackWrapper(SearchProvider):
    def __init__(
        self,
        providers: list[SearchProvider],
        *,
        role: str = "search",
        attempt_timeout: float | None = None,
        circuit_breaker_duration: float | None = None,
    ) -> None:
        self._providers = providers
        self._role = role
        self._attempt_timeout = attempt_timeout
        self._circuit_breaker_duration = circuit_breaker_duration

    async def search(self, query: str, **kwargs: Any) -> list[SearchResult]:
        return await run_provider_chain(
            providers=self._providers,
            operation="search",
            role=self._role,
            call=lambda p: p.search(query, **kwargs),
            attempt_timeout=self._attempt_timeout,
            circuit_breaker_duration=self._circuit_breaker_duration,
            unusable_result_hook=_search_unusable_hook,
        )
