import json
from collections.abc import Awaitable, Callable
from typing import Any
from urllib.parse import urlparse

from app.observability.provider_logging import log_provider_call
from app.providers.interfaces import (
    ImageAnalysisProvider,
    JudgeEvaluationProvider,
    ModelProvider,
    SearchProvider,
)
from app.providers.types import (
    ConfidenceLabel,
    ImageAnalysisResult,
    JudgeResult,
    JsonGenerationResult,
    PlantCandidate,
    SearchResult,
    TextGenerationResult,
)


class GeminiProviderError(RuntimeError):
    pass


def _client(api_key: str) -> Any:
    try:
        from google import genai
    except ImportError as exc:
        raise GeminiProviderError("The google-genai package is required for Gemini providers") from exc
    return genai.Client(api_key=api_key)


def _types() -> Any:
    try:
        from google.genai import types
    except ImportError as exc:
        raise GeminiProviderError("The google-genai package is required for Gemini providers") from exc
    return types


async def _logged(
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
        raise GeminiProviderError(f"Gemini {operation} call failed") from exc


class GeminiModelProvider(ModelProvider):
    provider_name = "gemini-model"

    def __init__(self, *, api_key: str, model: str, client: Any | None = None) -> None:
        self.model = model
        self._client = client or _client(api_key)

    async def generate_text(self, prompt: str, **kwargs: Any) -> TextGenerationResult:
        model = kwargs.pop("model", self.model)
        response = await _logged(
            provider=self.provider_name,
            role="model",
            operation="generate_text",
            call=lambda: _generate_content(
                self._client,
                model=model,
                contents=prompt,
                config=_generation_config(**kwargs),
            ),
        )
        return TextGenerationResult(provider=self.provider_name, model=model, text=_response_text(response))

    async def generate_json(
        self, prompt: str, schema: dict[str, Any], **kwargs: Any
    ) -> JsonGenerationResult:
        model = kwargs.pop("model", self.model)
        response = await _logged(
            provider=self.provider_name,
            role="model",
            operation="generate_json",
            call=lambda: _generate_content(
                self._client,
                model=model,
                contents=prompt,
                config=_json_generation_config(schema=schema, **kwargs),
            ),
        )
        return JsonGenerationResult(
            provider=self.provider_name,
            model=model,
            data=_json_from_response(response),
            metadata={"schema_keys": sorted(schema.keys())},
        )

    async def judge_response(
        self, payload: dict[str, Any], rubric: dict[str, Any], **kwargs: Any
    ) -> JudgeResult:
        judge = GeminiJudgeProvider(api_key="", model=self.model, client=self._client)
        return await judge.judge_response(payload, rubric, **kwargs)


class GeminiVisionProvider(ImageAnalysisProvider):
    provider_name = "gemini-vision"

    def __init__(self, *, api_key: str, model: str, client: Any | None = None) -> None:
        self.model = model
        self._client = client or _client(api_key)

    async def analyze_image(
        self, image: bytes, prompt: str | None = None, **kwargs: Any
    ) -> ImageAnalysisResult:
        mime_type = kwargs.pop("mime_type", "image/jpeg")
        model = kwargs.pop("model", self.model)
        prompt_text = _vision_prompt(prompt)
        response = await _logged(
            provider=self.provider_name,
            role="vision",
            operation="analyze_image",
            call=lambda: _generate_content(
                self._client,
                model=model,
                contents=_image_contents(prompt_text, image, mime_type),
                config=_json_generation_config(schema=_VISION_SCHEMA, **kwargs),
            ),
        )
        data = _json_from_response(response)
        candidates = [
            PlantCandidate(
                scientific_name=str(candidate.get("scientific_name") or "Unknown plant"),
                common_name=candidate.get("common_name"),
                confidence_label=_confidence_label(candidate.get("confidence_label")),
                confidence_score=candidate.get("confidence_score"),
                visible_traits=list(candidate.get("visible_traits") or []),
                provider=self.provider_name,
            )
            for candidate in data.get("candidates", [])
            if isinstance(candidate, dict)
        ][:3]
        return ImageAnalysisResult(
            provider=self.provider_name,
            model=model,
            description=str(data.get("description") or _response_text(response)),
            candidates=candidates,
            metadata={"image_size_bytes": len(image)},
        )


class GeminiSearchProvider(SearchProvider):
    provider_name = "gemini-search"

    def __init__(self, *, api_key: str, model: str, client: Any | None = None) -> None:
        self.model = model
        self._client = client or _client(api_key)

    async def search(self, query: str, **kwargs: Any) -> list[SearchResult]:
        allowed_domains = kwargs.pop("allowed_domains", None)
        model = kwargs.pop("model", self.model)
        response = await _logged(
            provider=self.provider_name,
            role="search",
            operation="search",
            call=lambda: _generate_content(
                self._client,
                model=model,
                contents=_search_prompt(query, allowed_domains),
                config=_search_generation_config(**kwargs),
            ),
        )
        return _search_results_from_response(response)


class GeminiJudgeProvider(JudgeEvaluationProvider):
    provider_name = "gemini-judge"

    def __init__(self, *, api_key: str, model: str, client: Any | None = None) -> None:
        self.model = model
        self._client = client or _client(api_key)

    async def judge_response(
        self, payload: dict[str, Any], rubric: dict[str, Any], **kwargs: Any
    ) -> JudgeResult:
        model = kwargs.pop("model", self.model)
        response = await _logged(
            provider=self.provider_name,
            role="judge",
            operation="judge_response",
            call=lambda: _generate_content(
                self._client,
                model=model,
                contents=_judge_prompt(payload, rubric),
                config=_json_generation_config(schema=_JUDGE_SCHEMA, **kwargs),
            ),
        )
        data = _json_from_response(response)
        return JudgeResult.from_provider_data(
            provider=self.provider_name,
            model=model,
            data=data,
            passing_score=float(rubric.get("passing_score", 1)),
        )


async def _generate_content(
    client: Any, *, model: str, contents: Any, config: Any | None = None
) -> Any:
    models = getattr(getattr(client, "aio", client), "models", None)
    if models is None or not hasattr(models, "generate_content"):
        raise GeminiProviderError("Gemini client did not expose aio.models.generate_content")
    return await models.generate_content(model=model, contents=contents, config=config)


def _generation_config(**kwargs: Any) -> Any | None:
    return _config_from_kwargs(**kwargs)


def _json_generation_config(schema: dict[str, Any], **kwargs: Any) -> Any:
    kwargs = dict(kwargs)
    kwargs.setdefault("response_mime_type", "application/json")
    kwargs.setdefault("response_schema", _gemini_response_schema(schema))
    return _config_from_kwargs(**kwargs) or kwargs


def _gemini_response_schema(schema: dict[str, Any]) -> dict[str, Any]:
    return _normalize_gemini_schema_value(schema)


def _normalize_gemini_schema_value(value: Any) -> Any:
    if isinstance(value, dict):
        normalized = {
            key: _normalize_gemini_schema_value(item) for key, item in value.items()
        }
        type_value = normalized.get("type")
        if isinstance(type_value, list) and "null" in type_value:
            non_null_types = [item for item in type_value if item != "null"]
            if len(non_null_types) == 1:
                normalized["type"] = non_null_types[0]
                normalized["nullable"] = True
        return normalized
    if isinstance(value, list):
        return [_normalize_gemini_schema_value(item) for item in value]
    return value


def _search_generation_config(**kwargs: Any) -> Any:
    kwargs = dict(kwargs)
    kwargs.setdefault("tools", [_google_search_tool()])
    return _config_from_kwargs(**kwargs) or kwargs


def _google_search_tool() -> Any:
    types = _types()
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


def _config_from_kwargs(**kwargs: Any) -> Any | None:
    if not kwargs:
        return None
    types = _types()
    config_type = getattr(types, "GenerateContentConfig", None)
    if config_type is None:
        return kwargs
    try:
        return config_type(**kwargs)
    except TypeError as exc:
        raise GeminiProviderError("Gemini generation config could not be constructed") from exc


def _image_contents(prompt: str, image: bytes, mime_type: str) -> list[Any]:
    types = _types()
    part_type = getattr(types, "Part", None)
    if part_type is None or not hasattr(part_type, "from_bytes"):
        return [prompt, {"inline_data": {"mime_type": mime_type, "data": image}}]
    return [prompt, part_type.from_bytes(data=image, mime_type=mime_type)]


def _response_text(response: Any) -> str:
    text = getattr(response, "text", None)
    if isinstance(text, str):
        return text
    text = getattr(response, "output_text", None)
    if isinstance(text, str):
        return text
    raise GeminiProviderError("Gemini response did not include text")


def _json_from_response(response: Any) -> dict[str, Any]:
    parsed = getattr(response, "parsed", None)
    if isinstance(parsed, dict):
        return parsed
    text = _response_text(response)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise GeminiProviderError("Gemini response was not valid JSON") from exc
    if not isinstance(data, dict):
        raise GeminiProviderError("Gemini JSON response must be an object")
    return data


def _confidence_label(value: Any) -> ConfidenceLabel:
    try:
        return ConfidenceLabel(str(value))
    except ValueError:
        return ConfidenceLabel.inconclusive


def _judge_prompt(payload: dict[str, Any], rubric: dict[str, Any]) -> str:
    return (
        "Evaluate the assistant output against the rubric. "
        "Return only valid JSON matching the rubric's expected_output.\n"
        f"Payload:\n{json.dumps(payload, ensure_ascii=True, sort_keys=True)}\n"
        f"Rubric:\n{json.dumps(rubric, ensure_ascii=True, sort_keys=True)}"
    )


def _search_prompt(query: str, allowed_domains: Any) -> str:
    prompt = (
        "Search the web for reliable botanical care or taxonomy sources using Google Search "
        "grounding. Return citation-backed sources only. Prefer primary, institutional, "
        f"or persistent reference pages. Query: {query}"
    )
    domains = _string_list(allowed_domains)
    if domains:
        prompt += "\nRestrict or strongly prefer results from these allowed domains: " + ", ".join(
            domains
        )
    return prompt


def _search_results_from_response(response: Any) -> list[SearchResult]:
    text = _optional_response_text(response)
    results: list[SearchResult] = []
    seen_urls: set[str] = set()
    grounding_metadata_seen = False
    for metadata in _grounding_metadata(response):
        grounding_metadata_seen = True
        chunks = _iter_any(_value(metadata, "grounding_chunks"))
        supports = _iter_any(_value(metadata, "grounding_supports"))
        snippets_by_index = _grounding_snippets_by_index(supports, text)
        for index, chunk in enumerate(chunks):
            web = _value(chunk, "web") or chunk
            url = str(_value(web, "uri") or _value(web, "url") or "").strip()
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc or url in seen_urls:
                continue
            seen_urls.add(url)
            title = str(_value(web, "title") or parsed.netloc).strip()
            snippet = snippets_by_index.get(index) or title
            results.append(
                SearchResult(
                    title=title,
                    url=url,
                    snippet=snippet,
                    source_domain=parsed.netloc.lower(),
                )
            )
    if not grounding_metadata_seen:
        raise GeminiProviderError("Gemini search grounding metadata was unavailable")
    return results


def _grounding_metadata(response: Any) -> list[Any]:
    metadata: list[Any] = []
    direct = _value(response, "grounding_metadata")
    if direct is not None:
        metadata.append(direct)
    for candidate in _iter_any(_value(response, "candidates")):
        candidate_metadata = _value(candidate, "grounding_metadata")
        if candidate_metadata is not None:
            metadata.append(candidate_metadata)
    return metadata


def _grounding_snippets_by_index(supports: list[Any], text: str) -> dict[int, str]:
    snippets: dict[int, str] = {}
    for support in supports:
        segment = _value(support, "segment")
        snippet = str(_value(segment, "text") or "").strip()
        if not snippet:
            start = _value(segment, "start_index")
            end = _value(segment, "end_index")
            if isinstance(start, int) and isinstance(end, int) and 0 <= start < end <= len(text):
                snippet = text[start:end].strip()
        if not snippet:
            continue
        for index in _iter_any(_value(support, "grounding_chunk_indices")):
            if isinstance(index, int) and index not in snippets:
                snippets[index] = snippet
    return snippets


def _optional_response_text(response: Any) -> str:
    try:
        return _response_text(response)
    except GeminiProviderError:
        return ""


def _value(value: Any, key: str) -> Any:
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key, None)


def _iter_any(value: Any) -> list[Any]:
    if isinstance(value, list | tuple):
        return list(value)
    return []


def _string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list | tuple | set):
        return [str(item) for item in value if str(item).strip()]
    return []


def _vision_prompt(prompt: str | None) -> str:
    base_prompt = prompt.strip() if prompt else _VISION_PROMPT
    return (
        f"{base_prompt}\n"
        "Return only valid JSON with this structure: "
        '{"description": string, "candidates": ['
        '{"scientific_name": string, "common_name": string | null, '
        '"confidence_label": "high" | "medium" | "low" | "inconclusive", '
        '"confidence_score": number | null, "visible_traits": string[]}]} '
        "Return at most three candidates."
    )


_VISION_PROMPT = """
Analyze this plant image. Return JSON with description and candidates. Each candidate must include
scientific_name, common_name, confidence_label, confidence_score and visible_traits.
""".strip()


_VISION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "description": {"type": "string"},
        "candidates": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "scientific_name": {"type": "string"},
                    "common_name": {"type": "string", "nullable": True},
                    "confidence_label": {
                        "type": "string",
                        "enum": ["high", "medium", "low", "inconclusive"],
                    },
                    "confidence_score": {"type": "number", "nullable": True},
                    "visible_traits": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["scientific_name", "visible_traits"],
            },
        },
    },
    "required": ["description", "candidates"],
}


_JUDGE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "status": {"type": "string", "enum": ["full", "partial", "insufficient", "contradictory"]},
        "covered_aspects": {"type": "array", "items": {"type": "string"}},
        "missing_aspects": {"type": "array", "items": {"type": "string"}},
        "source_support": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "claim": {"type": "string"},
                    "source_urls": {"type": "array", "items": {"type": "string"}},
                    "covered_aspects": {"type": "array", "items": {"type": "string"}},
                    "evidence_quote": {"type": "string"},
                    "confidence": {"type": "number"},
                },
                "required": ["claim", "source_urls", "covered_aspects", "evidence_quote", "confidence"],
            },
        },
        "contradictions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "claim_a": {"type": "string"},
                    "claim_b": {"type": "string"},
                    "source_a_urls": {"type": "array", "items": {"type": "string"}},
                    "source_b_urls": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["claim_a", "claim_b", "source_a_urls", "source_b_urls"],
            },
        },
        "confidence": {"type": "number"},
        "score": {"type": "number"},
        "passed": {"type": "boolean"},
        "reasons": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "status",
        "covered_aspects",
        "missing_aspects",
        "source_support",
        "contradictions",
        "confidence",
        "score",
        "passed",
        "reasons",
    ],
}
