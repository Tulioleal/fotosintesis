"""Gemini response configuration builders."""

from __future__ import annotations

from typing import Any

from app.providers.errors import GeminiProviderError
from app.providers.gemini._client import config_from_kwargs, gemini_types


def generation_config(**kwargs: Any) -> Any | None:
    return config_from_kwargs(**kwargs)


def json_generation_config(schema: dict[str, Any], **kwargs: Any) -> Any:
    kwargs = dict(kwargs)
    kwargs.setdefault("response_mime_type", "application/json")
    kwargs.setdefault("response_schema", normalize_gemini_schema(schema))
    return config_from_kwargs(**kwargs) or kwargs


def normalize_gemini_schema(value: Any) -> Any:
    if isinstance(value, dict):
        normalized = {
            key: normalize_gemini_schema(item) for key, item in value.items()
        }
        type_value = normalized.get("type")
        if isinstance(type_value, list) and "null" in type_value:
            non_null_types = [item for item in type_value if item != "null"]
            if len(non_null_types) == 1:
                normalized["type"] = non_null_types[0]
                normalized["nullable"] = True
        return normalized
    if isinstance(value, list):
        return [normalize_gemini_schema(item) for item in value]
    return value


def search_generation_config(**kwargs: Any) -> Any:
    kwargs = dict(kwargs)
    kwargs.setdefault("tools", [google_search_tool()])
    return config_from_kwargs(**kwargs) or kwargs


def google_search_tool() -> Any:
    types = gemini_types()
    tool_type = getattr(types, "Tool", None)
    google_search_type = getattr(types, "GoogleSearch", None)
    if tool_type is None or google_search_type is None:
        raise GeminiProviderError("Gemini Google Search grounding tool is unavailable")
    try:
        return tool_type(google_search=google_search_type())
    except TypeError as exc:
        google_search_retrieval_type = getattr(types, "GoogleSearchRetrieval", None)
        if google_search_retrieval_type is None:
            raise GeminiProviderError("Gemini Google Search grounding tool is unavailable") from exc
        try:
            return tool_type(google_search_retrieval=google_search_retrieval_type())
        except TypeError as fallback_exc:
            raise GeminiProviderError("Gemini Google Search grounding tool is unavailable") from fallback_exc


def image_contents(prompt: str, image: bytes, mime_type: str) -> list[Any]:
    types = gemini_types()
    part_type = getattr(types, "Part", None)
    if part_type is None or not hasattr(part_type, "from_bytes"):
        return [prompt, {"inline_data": {"mime_type": mime_type, "data": image}}]
    return [prompt, part_type.from_bytes(data=image, mime_type=mime_type)]
