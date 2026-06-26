"""Gemini web search provider (Google Search grounding)."""

from __future__ import annotations

from urllib.parse import urlparse
from typing import Any

from app.providers.errors import GeminiProviderError
from app.providers.gemini._client import (
    generate_content,
    gemini_client,
    iter_any,
    logged_call,
    optional_response_text,
    string_list,
    value,
)
from app.providers.gemini.configs import search_generation_config
from app.providers.interfaces import SearchProvider
from app.providers.types import SearchResult


def _search_prompt(query: str, allowed_domains: Any) -> str:
    prompt = (
        "Search the web for reliable botanical care or taxonomy sources using Google Search "
        "grounding. Return citation-backed sources only. Prefer primary, institutional, "
        f"or persistent reference pages. Query: {query}"
    )
    domains = string_list(allowed_domains)
    if domains:
        prompt += "\nRestrict or strongly prefer results from these allowed domains: " + ", ".join(
            domains
        )
    return prompt


def _is_internal_redirect_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.netloc.endswith(".google.com") or parsed.netloc.endswith(".google"):
        return True
    path = parsed.path.lower()
    return (
        "redirect" in path
        or "search" in path
        or "url?q=" in parsed.query
        or parsed.netloc.endswith(".googleusercontent.com")
    )


def _grounding_metadata(response: Any) -> list[Any]:
    metadata: list[Any] = []
    direct = value(response, "grounding_metadata")
    if direct is not None:
        metadata.append(direct)
    for candidate in iter_any(value(response, "candidates")):
        candidate_metadata = value(candidate, "grounding_metadata")
        if candidate_metadata is not None:
            metadata.append(candidate_metadata)
    return metadata


def _grounding_snippets_by_index(supports: list[Any], text: str) -> dict[int, str]:
    snippets: dict[int, str] = {}
    for support in supports:
        segment = value(support, "segment")
        snippet = str(value(segment, "text") or "").strip()
        if not snippet:
            start = value(segment, "start_index")
            end = value(segment, "end_index")
            if isinstance(start, int) and isinstance(end, int) and 0 <= start < end <= len(text):
                snippet = text[start:end].strip()
        if not snippet:
            continue
        for index in iter_any(value(support, "grounding_chunk_indices")):
            if isinstance(index, int) and index not in snippets:
                snippets[index] = snippet
    return snippets


def _search_results_from_response(response: Any) -> list[SearchResult]:
    text = optional_response_text(response)
    results: list[SearchResult] = []
    seen_urls: set[str] = set()
    grounding_metadata_seen = False
    for metadata in _grounding_metadata(response):
        grounding_metadata_seen = True
        chunks = iter_any(value(metadata, "grounding_chunks"))
        supports = iter_any(value(metadata, "grounding_supports"))
        snippets_by_index = _grounding_snippets_by_index(supports, text)
        for index, chunk in enumerate(chunks):
            web = value(chunk, "web") or chunk
            url = str(value(web, "uri") or value(web, "url") or "").strip()
            if not url or url in seen_urls:
                continue
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                continue
            if _is_internal_redirect_url(url):
                continue
            seen_urls.add(url)
            title = str(value(web, "title") or parsed.netloc).strip()
            support_snippet = snippets_by_index.get(index)
            snippet = support_snippet or title
            results.append(
                SearchResult(
                    title=title,
                    url=url,
                    snippet=snippet,
                    source_domain=parsed.netloc.lower(),
                    metadata={
                        "snippet_source": "grounding_support" if support_snippet else "title_fallback"
                    },
                )
            )
    if not grounding_metadata_seen:
        raise GeminiProviderError("Gemini search grounding metadata was unavailable")
    return results


class GeminiSearchProvider(SearchProvider):
    provider_name = "gemini-search"

    def __init__(self, *, api_key: str, model: str, client: Any | None = None) -> None:
        self.model = model
        self._client = client or gemini_client(api_key)

    async def search(self, query: str, **kwargs: Any) -> list[SearchResult]:
        allowed_domains = kwargs.pop("allowed_domains", None)
        model = kwargs.pop("model", self.model)
        response = await logged_call(
            provider=self.provider_name,
            role="search",
            operation="search",
            call=lambda: generate_content(
                self._client,
                model=model,
                contents=_search_prompt(query, allowed_domains),
                config=search_generation_config(**kwargs),
            ),
        )
        return _search_results_from_response(response)
