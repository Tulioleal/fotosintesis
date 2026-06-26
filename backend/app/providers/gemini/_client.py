"""Gemini client wiring and shared response-parsing helpers."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any

from app.observability.provider_logging import log_provider_call
from app.providers.errors import GeminiProviderError


def gemini_client(api_key: str) -> Any:
    try:
        from google import genai
    except ImportError as exc:
        raise GeminiProviderError("The google-genai package is required for Gemini providers") from exc
    return genai.Client(api_key=api_key)


def gemini_types() -> Any:
    try:
        from google.genai import types
    except ImportError as exc:
        raise GeminiProviderError("The google-genai package is required for Gemini providers") from exc
    return types


async def logged_call(
    *,
    provider: str,
    role: str,
    operation: str,
    call: Callable[[], Awaitable[Any]],
) -> Any:
    try:
        return await log_provider_call(provider, operation, call, role=role)
    except GeminiProviderError:
        raise
    except Exception as exc:
        raise GeminiProviderError(
            f"Gemini {operation} call failed",
            original_exception=exc,
        ) from exc


async def generate_content(
    client: Any, *, model: str, contents: Any, config: Any | None = None
) -> Any:
    models = getattr(getattr(client, "aio", client), "models", None)
    if models is None or not hasattr(models, "generate_content"):
        raise GeminiProviderError("Gemini client did not expose aio.models.generate_content")
    return await models.generate_content(model=model, contents=contents, config=config)


def config_from_kwargs(**kwargs: Any) -> Any | None:
    if not kwargs:
        return None
    types = gemini_types()
    config_type = getattr(types, "GenerateContentConfig", None)
    if config_type is None:
        return kwargs
    try:
        return config_type(**kwargs)
    except TypeError as exc:
        raise GeminiProviderError("Gemini generation config could not be constructed") from exc


def response_text(response: Any) -> str:
    text = getattr(response, "text", None)
    if isinstance(text, str):
        return text
    text = getattr(response, "output_text", None)
    if isinstance(text, str):
        return text
    raise GeminiProviderError("Gemini response did not include text")


def optional_response_text(response: Any) -> str:
    try:
        return response_text(response)
    except GeminiProviderError:
        return ""


def json_from_response(response: Any) -> dict[str, Any]:
    parsed = getattr(response, "parsed", None)
    if isinstance(parsed, dict):
        return parsed
    text = response_text(response)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise GeminiProviderError("Gemini response was not valid JSON") from exc
    if not isinstance(data, dict):
        raise GeminiProviderError("Gemini JSON response must be an object")
    return data


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
