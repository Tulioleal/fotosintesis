"""OpenAI client wiring and shared response-parsing helpers."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any
from urllib.parse import urlparse

from app.observability.logging import get_logger
from app.observability.provider_logging import log_provider_call
from app.providers.errors import OpenAIProviderError
from app.providers.types import SearchResult

logger = get_logger(__name__)


def openai_client(api_key: str) -> Any:
    try:
        from openai import AsyncOpenAI
    except ImportError as exc:
        raise OpenAIProviderError("The openai package is required for OpenAI providers") from exc
    return AsyncOpenAI(api_key=api_key)


async def logged_call(
    *,
    provider: str,
    role: str,
    operation: str,
    call: Callable[[], Awaitable[Any]],
) -> Any:
    return await log_provider_call(provider, operation, call, role=role)


def response_text(response: Any) -> str:
    text = getattr(response, "output_text", None)
    if isinstance(text, str):
        return text
    raise OpenAIProviderError("OpenAI response did not include output_text")


def json_from_response(response: Any) -> dict[str, Any]:
    text = response_text(response)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise OpenAIProviderError("OpenAI response was not valid JSON") from exc
    if not isinstance(data, dict):
        raise OpenAIProviderError("OpenAI JSON response must be an object")
    return data


def response_annotations(response: Any) -> list[Any]:
    annotations: list[Any] = []
    for output in iter_any(getattr(response, "output", None)):
        for content in iter_any(value(output, "content")):
            annotations.extend(iter_any(value(content, "annotations")))
    return annotations


def citation_snippet(annotation: Any, text: str) -> str:
    start = annotation_value(annotation, "start_index")
    end = annotation_value(annotation, "end_index")
    if isinstance(start, int) and isinstance(end, int) and 0 <= start < end <= len(text):
        return text[start:end].strip()
    return text.strip()


def annotation_value(annotation: Any, key: str) -> Any:
    return value(annotation, key)


def value(value_obj: Any, key: str) -> Any:
    if isinstance(value_obj, dict):
        return value_obj.get(key)
    return getattr(value_obj, key, None)


def iter_any(value_obj: Any) -> list[Any]:
    if isinstance(value_obj, list | tuple):
        return list(value_obj)
    return []


def string_list(value_obj: Any) -> list[str]:
    if isinstance(value_obj, str):
        return [value_obj]
    if isinstance(value_obj, list | tuple | set):
        return [str(item) for item in value_obj if str(item).strip()]
    return []


def search_results_from_response(response: Any) -> list[SearchResult]:
    text = getattr(response, "output_text", "")
    if not isinstance(text, str):
        text = ""
    results: list[SearchResult] = []
    seen_urls: set[str] = set()
    has_annotations = False
    for annotation in response_annotations(response):
        if annotation_value(annotation, "type") != "url_citation":
            continue
        has_annotations = True
        url = str(annotation_value(annotation, "url") or "").strip()
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc or url in seen_urls:
            continue
        seen_urls.add(url)
        title = str(annotation_value(annotation, "title") or parsed.netloc).strip()
        snippet = citation_snippet(annotation, text) or title
        results.append(
            SearchResult(
                title=title,
                url=url,
                snippet=snippet,
                source_domain=parsed.netloc.lower(),
            )
        )
    if not has_annotations:
        return results
    return results
