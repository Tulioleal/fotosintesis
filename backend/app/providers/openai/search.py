"""OpenAI web search provider."""

from __future__ import annotations

from typing import Any

from app.providers.interfaces import SearchProvider
from app.providers.openai._client import (
    logged_call,
    openai_client,
    search_results_from_response,
    string_list,
)
from app.providers.types import SearchResult


def _search_prompt(query: str, allowed_domains: Any) -> str:
    prompt = (
        "Search the web for reliable botanical care or taxonomy sources. "
        "Prefer primary, institutional, or persistent reference pages. "
        f"Query: {query}"
    )
    domains = string_list(allowed_domains)
    if domains:
        prompt += "\nPrefer results from these allowed domains: " + ", ".join(domains)
    return prompt


class OpenAISearchProvider(SearchProvider):
    provider_name = "openai-search"

    def __init__(self, *, api_key: str, model: str) -> None:
        self.model = model
        self._client = openai_client(api_key)

    async def search(self, query: str, **kwargs: Any) -> list[SearchResult]:
        allowed_domains = kwargs.pop("allowed_domains", None)
        model = kwargs.pop("model", self.model)
        response = await logged_call(
            provider=self.provider_name,
            role="search",
            operation="search",
            call=lambda: self._client.responses.create(
                model=model,
                input=_search_prompt(query, allowed_domains),
                tools=[{"type": "web_search"}],
                **kwargs,
            ),
        )
        return search_results_from_response(response)
