"""Gemini web search provider (Google Search grounding)."""

from __future__ import annotations

import asyncio
import http.client
from concurrent.futures import ThreadPoolExecutor
from typing import Any
from urllib.parse import parse_qs, urljoin, urlparse

from app.observability.logging import get_logger
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


logger = get_logger(__name__)
_REDIRECT_QUERY_KEYS = ("q", "url", "target")
_MAX_GROUNDING_REDIRECTS = 3


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
    hostname = (parsed.hostname or "").lower()
    if (
        hostname == "google.com"
        or hostname.endswith(".google.com")
        or hostname == "googleusercontent.com"
        or hostname.endswith(".googleusercontent.com")
    ):
        return True
    return False


def _hostname_allowed(hostname: str, allowed_domains: set[str]) -> bool:
    normalized = hostname.lower().rstrip(".")
    return any(
        normalized == domain or normalized.endswith(f".{domain}")
        for domain in allowed_domains
    )


def _query_redirect_target(url: str) -> str | None:
    query = parse_qs(urlparse(url).query)
    for key in _REDIRECT_QUERY_KEYS:
        values = query.get(key)
        if values and values[0].startswith("https://"):
            return values[0]
    return None


def _resolve_grounding_redirect(
    url: str,
    allowed_domains: set[str],
    *,
    connection_factory: Any | None = None,
) -> str | None:
    """Resolve bounded Google grounding redirects without fetching the destination."""
    current = url
    for _ in range(_MAX_GROUNDING_REDIRECTS):
        query_target = _query_redirect_target(current)
        if query_target is not None:
            target_host = urlparse(query_target).hostname or ""
            return query_target if _hostname_allowed(target_host, allowed_domains) else None

        parsed = urlparse(current)
        hostname = parsed.hostname or ""
        if parsed.scheme != "https" or not _is_internal_redirect_url(current):
            return None
        port = parsed.port or 443
        path = parsed.path or "/"
        if parsed.query:
            path = f"{path}?{parsed.query}"
        connection = (
            connection_factory(hostname, port)
            if connection_factory is not None
            else http.client.HTTPSConnection(hostname, port, timeout=4)
        )
        try:
            connection.request(
                "GET",
                path,
                headers={"User-Agent": "FotosintesisBot/1.0", "Accept": "text/html"},
            )
            response = connection.getresponse()
            location = response.getheader("location")
        except OSError:
            return None
        finally:
            connection.close()
        if not location:
            return None
        target = urljoin(current, location)
        target_host = urlparse(target).hostname or ""
        if _hostname_allowed(target_host, allowed_domains):
            return target
        current = target
    return None


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


def _chunk_url(chunk: Any) -> str:
    web = value(chunk, "web") or chunk
    return str(value(web, "uri") or value(web, "url") or "").strip()


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


def _search_results_from_response(
    response: Any,
    *,
    allowed_domains: Any = None,
    resolve_redirects: bool = False,
) -> list[SearchResult]:
    text = optional_response_text(response)
    results: list[SearchResult] = []
    seen_urls: set[str] = set()
    metadata_items = _grounding_metadata(response)
    grounding_metadata_seen = bool(metadata_items)
    chunks_seen = 0
    rejected_urls = 0
    approved_domains = {
        domain.lower().rstrip(".") for domain in string_list(allowed_domains)
    }
    resolved_redirects: dict[str, str | None] = {}
    if resolve_redirects and approved_domains:
        redirect_urls = {
            _chunk_url(chunk)
            for metadata in metadata_items
            for chunk in iter_any(value(metadata, "grounding_chunks"))
        }
        redirect_urls = {url for url in redirect_urls if _is_internal_redirect_url(url)}
        if redirect_urls:
            with ThreadPoolExecutor(max_workers=min(8, len(redirect_urls))) as executor:
                resolved_redirects = dict(
                    zip(
                        redirect_urls,
                        executor.map(
                            lambda url: _resolve_grounding_redirect(url, approved_domains),
                            redirect_urls,
                        ),
                        strict=True,
                    )
                )

    for metadata in metadata_items:
        chunks = iter_any(value(metadata, "grounding_chunks"))
        supports = iter_any(value(metadata, "grounding_supports"))
        snippets_by_index = _grounding_snippets_by_index(supports, text)
        for index, chunk in enumerate(chunks):
            chunks_seen += 1
            web = value(chunk, "web") or chunk
            url = _chunk_url(chunk)
            if not url:
                rejected_urls += 1
                continue
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                rejected_urls += 1
                continue
            if _is_internal_redirect_url(url) and not _hostname_allowed(
                parsed.hostname or "", approved_domains
            ):
                if not (resolve_redirects and approved_domains):
                    rejected_urls += 1
                    continue
                url = resolved_redirects.get(url) or ""
                parsed = urlparse(url)
                if not url or not parsed.hostname:
                    rejected_urls += 1
                    continue
            if url in seen_urls:
                rejected_urls += 1
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
    logger.info(
        "gemini_search_grounding_normalized",
        extra={
            "ctx_grounding_chunks": chunks_seen,
            "ctx_rejected_urls": rejected_urls,
            "ctx_accepted_urls": len(results),
        },
    )
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
        return await asyncio.to_thread(
            _search_results_from_response,
            response,
            allowed_domains=allowed_domains,
            resolve_redirects=True,
        )
