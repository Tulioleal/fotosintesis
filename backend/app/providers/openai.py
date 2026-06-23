import base64
import json
from collections.abc import Awaitable, Callable
from typing import Any
from urllib.parse import urlparse

from app.observability.logging import get_logger
from app.observability.provider_logging import log_provider_call
from app.providers.interfaces import (
    EmbeddingProvider,
    ImageAnalysisProvider,
    JudgeEvaluationProvider,
    ModelProvider,
    SearchProvider,
)
from app.providers.types import (
    ConfidenceLabel,
    EmbeddingResult,
    ImageAnalysisResult,
    JudgeResult,
    JsonGenerationResult,
    PlantCandidate,
    SearchResult,
    TextGenerationResult,
)


logger = get_logger(__name__)


class OpenAIProviderError(RuntimeError):
    pass


def _client(api_key: str) -> Any:
    try:
        from openai import AsyncOpenAI
    except ImportError as exc:
        raise OpenAIProviderError("The openai package is required for OpenAI providers") from exc
    return AsyncOpenAI(api_key=api_key)


def _response_text(response: Any) -> str:
    text = getattr(response, "output_text", None)
    if isinstance(text, str):
        return text
    raise OpenAIProviderError("OpenAI response did not include output_text")


def _json_from_response(response: Any) -> dict[str, Any]:
    text = _response_text(response)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise OpenAIProviderError("OpenAI response was not valid JSON") from exc
    if not isinstance(data, dict):
        raise OpenAIProviderError("OpenAI JSON response must be an object")
    return data


async def _logged(
    *,
    provider: str,
    role: str,
    operation: str,
    call: Callable[[], Awaitable[Any]],
) -> Any:
    return await log_provider_call(provider, operation, call, role=role)


_STRICT_UNSUPPORTED_KEYS = frozenset({
    "$ref",
    "$dynamicRef",
    "$anchor",
    "$id",
    "$schema",
    "oneOf",
    "allOf",
    "not",
    "if",
    "then",
    "else",
    "dependencies",
    "dependentSchemas",
    "dependentRequired",
    "patternProperties",
    "additionalItems",
    "unevaluatedProperties",
    "unevaluatedItems",
})

_STRICT_SCALAR_TYPES = frozenset({"string", "number", "integer", "boolean"})


def _to_openai_strict_schema(schema: Any) -> dict[str, Any] | None:
    """Convert a JSON Schema fragment into an OpenAI strict-mode compatible form.

    Returns a sanitized copy with the following transformations:

    - All object schemas have ``additionalProperties: false`` and a complete
      ``required`` list (every property is marked as required, matching the
      strict-mode requirement that all properties be present in every
      response).
    - ``description`` and ``enum`` values are preserved.
    - Nullable scalar fields written as ``{"type": ["string", "null"]}`` are
      preserved verbatim because OpenAI strict mode accepts that list-of-types
      form.
    - Nested object, array, and scalar subschemas are normalized recursively.

    Returns ``None`` when the schema contains any construct that strict mode
    does not accept (e.g. ``$ref``, ``oneOf``, ``allOf``, ``patternProperties``)
    or when the input is not a JSON-Schema-shaped object. The caller is
    expected to fall back to JSON object mode whenever ``None`` is returned.
    """

    try:
        normalized = _sanitize_strict_node(schema)
    except _StrictSchemaUnsupported:
        return None
    if not isinstance(normalized, dict):
        return None
    if normalized.get("type") != "object":
        return None
    return normalized


def _sanitize_strict_node(node: Any) -> Any:
    if node is None:
        return None
    if not isinstance(node, dict):
        raise _StrictSchemaUnsupported()
    for key in node:
        if key in _STRICT_UNSUPPORTED_KEYS:
            raise _StrictSchemaUnsupported()
    raw_type = node.get("type")
    if isinstance(raw_type, list):
        return _sanitize_union_type(node, raw_type)
    if raw_type is None:
        if "enum" in node:
            return _sanitize_enum_node(node)
        if "properties" in node or "additionalProperties" in node:
            return _sanitize_object_node(node)
        if "items" in node:
            return _sanitize_array_node(node)
        return _sanitize_scalar_node(node)
    if raw_type in _STRICT_SCALAR_TYPES:
        return _sanitize_scalar_node(node)
    if raw_type == "array":
        return _sanitize_array_node(node)
    if raw_type == "object":
        return _sanitize_object_node(node)
    if raw_type == "null":
        return {"type": "null"}
    raise _StrictSchemaUnsupported()


def _sanitize_union_type(node: dict[str, Any], types: list[Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key, value in node.items():
        if key == "type":
            continue
        sanitized[key] = _copy_passthrough(value)
    normalized_types: list[Any] = []
    for entry in types:
        if not isinstance(entry, str):
            raise _StrictSchemaUnsupported()
        if entry == "null":
            normalized_types.append("null")
            continue
        if entry in _STRICT_SCALAR_TYPES or entry in {"array", "object"}:
            normalized_types.append(entry)
            continue
        raise _StrictSchemaUnsupported()
    if not normalized_types:
        raise _StrictSchemaUnsupported()
    sanitized["type"] = normalized_types
    return sanitized


def _sanitize_scalar_node(node: dict[str, Any]) -> dict[str, Any]:
    raw_type = node.get("type")
    if isinstance(raw_type, list):
        return _sanitize_union_type(node, raw_type)
    if raw_type not in _STRICT_SCALAR_TYPES:
        raise _StrictSchemaUnsupported()
    sanitized: dict[str, Any] = {"type": raw_type}
    if "enum" in node and isinstance(node["enum"], list):
        sanitized["enum"] = [_enum_value(value) for value in node["enum"]]
    if "description" in node and isinstance(node["description"], str):
        sanitized["description"] = node["description"]
    if "minimum" in node and isinstance(node["minimum"], (int, float)):
        sanitized["minimum"] = node["minimum"]
    if "maximum" in node and isinstance(node["maximum"], (int, float)):
        sanitized["maximum"] = node["maximum"]
    return sanitized


def _sanitize_enum_node(node: dict[str, Any]) -> dict[str, Any]:
    values = node.get("enum")
    if not isinstance(values, list) or not values:
        raise _StrictSchemaUnsupported()
    sanitized: dict[str, Any] = {"enum": [_enum_value(value) for value in values]}
    raw_type = node.get("type")
    if isinstance(raw_type, str) and raw_type in _STRICT_SCALAR_TYPES:
        sanitized["type"] = raw_type
    if "description" in node and isinstance(node["description"], str):
        sanitized["description"] = node["description"]
    return sanitized


def _sanitize_array_node(node: dict[str, Any]) -> dict[str, Any]:
    items = node.get("items")
    if items is None:
        raise _StrictSchemaUnsupported()
    sanitized: dict[str, Any] = {"type": "array", "items": _sanitize_strict_node(items)}
    if "description" in node and isinstance(node["description"], str):
        sanitized["description"] = node["description"]
    if "minItems" in node and isinstance(node["minItems"], int):
        sanitized["minItems"] = node["minItems"]
    if "maxItems" in node and isinstance(node["maxItems"], int):
        sanitized["maxItems"] = node["maxItems"]
    return sanitized


def _sanitize_object_node(node: dict[str, Any]) -> dict[str, Any]:
    properties = node.get("properties")
    if not isinstance(properties, dict) or not properties:
        raise _StrictSchemaUnsupported()
    sanitized_properties: dict[str, Any] = {}
    for name, value in properties.items():
        if not isinstance(name, str) or not name:
            raise _StrictSchemaUnsupported()
        sanitized_properties[name] = _sanitize_strict_node(value)
    required = list(sanitized_properties.keys())
    sanitized: dict[str, Any] = {
        "type": "object",
        "properties": sanitized_properties,
        "required": required,
        "additionalProperties": False,
    }
    if "description" in node and isinstance(node["description"], str):
        sanitized["description"] = node["description"]
    return sanitized


def _copy_passthrough(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _copy_passthrough(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_copy_passthrough(item) for item in value]
    return value


def _enum_value(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _log_provider_json_schema_fallback(
    *,
    provider: str,
    role: str,
    operation: str,
    schema_name: str | None,
    reason: str,
) -> None:
    logger.info(
        "provider json schema fallback",
        extra={
            "ctx_event": "provider_json_schema_fallback",
            "ctx_provider": provider,
            "ctx_role": role,
            "ctx_operation": operation,
            "ctx_schema_name": schema_name,
            "ctx_reason": reason,
        },
    )


def _build_strict_text_format(
    *,
    schema: Any,
    name: str,
    provider: str,
    role: str,
    operation: str,
) -> dict[str, Any] | None:
    sanitized = _to_openai_strict_schema(schema)
    if sanitized is None:
        _log_provider_json_schema_fallback(
            provider=provider,
            role=role,
            operation=operation,
            schema_name=name,
            reason="schema cannot be safely sanitized for strict mode",
        )
        return None
    return {
        "type": "json_schema",
        "name": name,
        "schema": sanitized,
        "strict": True,
    }


class _StrictSchemaUnsupported(Exception):
    pass


class OpenAIModelProvider(ModelProvider):
    provider_name = "openai-model"

    def __init__(
        self, *, api_key: str, model: str, classifier_model: str | None = None
    ) -> None:
        self.model = model
        self.classifier_model = classifier_model or model
        self._client = _client(api_key)

    def _resolve_model(self, kwargs: dict[str, Any]) -> str:
        explicit = kwargs.pop("model", None)
        if explicit is not None:
            return explicit
        purpose = kwargs.pop("model_purpose", None)
        if purpose == "classifier":
            return self.classifier_model
        return self.model

    async def generate_text(self, prompt: str, **kwargs: Any) -> TextGenerationResult:
        selected_model = self._resolve_model(kwargs)
        response = await _logged(
            provider=self.provider_name,
            role="model",
            operation="generate_text",
            call=lambda: self._client.responses.create(
                model=selected_model,
                input=prompt,
                **kwargs,
            ),
        )
        return TextGenerationResult(
            provider=self.provider_name,
            model=selected_model,
            text=_response_text(response),
        )

    async def generate_json(
        self, prompt: str, schema: dict[str, Any], **kwargs: Any
    ) -> JsonGenerationResult:
        selected_model = self._resolve_model(kwargs)
        text_format = _build_strict_text_format(
            schema=schema,
            name="care_classifier",
            provider=self.provider_name,
            role="model",
            operation="generate_json",
        )
        if text_format is None:
            text_format = {"format": {"type": "json_object"}}
        else:
            text_format = {"format": text_format}
        response = await _logged(
            provider=self.provider_name,
            role="model",
            operation="generate_json",
            call=lambda: self._client.responses.create(
                model=selected_model,
                input=prompt,
                text=text_format,
                **kwargs,
            ),
        )
        return JsonGenerationResult(
            provider=self.provider_name,
            model=selected_model,
            data=_json_from_response(response),
            metadata={"schema_keys": sorted(schema.keys())},
        )

    async def judge_response(
        self, payload: dict[str, Any], rubric: dict[str, Any], **kwargs: Any
    ) -> JudgeResult:
        judge = OpenAIJudgeProvider(api_key="", model=self.model, client=self._client)
        return await judge.judge_response(payload, rubric, **kwargs)


class OpenAIVisionProvider(ImageAnalysisProvider):
    provider_name = "openai-vision"

    def __init__(self, *, api_key: str, model: str) -> None:
        self.model = model
        self._client = _client(api_key)

    async def analyze_image(
        self, image: bytes, prompt: str | None = None, **kwargs: Any
    ) -> ImageAnalysisResult:
        mime_type = kwargs.pop("mime_type", "image/jpeg")
        model = kwargs.pop("model", self.model)
        image_url = f"data:{mime_type};base64,{base64.b64encode(image).decode('ascii')}"
        prompt_text = _vision_prompt(prompt)
        text_format = _build_strict_text_format(
            schema=_VISION_SCHEMA,
            name="plant_image_analysis",
            provider=self.provider_name,
            role="vision",
            operation="analyze_image",
        )
        text_kwargs = (
            {"format": text_format} if text_format is not None else {"format": {"type": "json_object"}}
        )
        response = await _logged(
            provider=self.provider_name,
            role="vision",
            operation="analyze_image",
            call=lambda: self._client.responses.create(
                model=model,
                input=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "input_text",
                                "text": prompt_text,
                            },
                            {"type": "input_image", "image_url": image_url},
                        ],
                    }
                ],
                text=text_kwargs,
                **kwargs,
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
        ]
        return ImageAnalysisResult(
            provider=self.provider_name,
            model=self.model,
            description=str(data.get("description") or _response_text(response)),
            candidates=candidates,
            metadata={"image_size_bytes": len(image)},
        )


class OpenAISearchProvider(SearchProvider):
    provider_name = "openai-search"

    def __init__(self, *, api_key: str, model: str) -> None:
        self.model = model
        self._client = _client(api_key)

    async def search(self, query: str, **kwargs: Any) -> list[SearchResult]:
        allowed_domains = kwargs.pop("allowed_domains", None)
        model = kwargs.pop("model", self.model)
        response = await _logged(
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
        return _search_results_from_response(response)


class OpenAIEmbeddingProvider(EmbeddingProvider):
    provider_name = "openai-embedding"

    def __init__(self, *, api_key: str, model: str, embedding_dimension: int | None = None) -> None:
        self.model = model
        self.embedding_dimension = embedding_dimension
        self._client = _client(api_key)

    async def create_embeddings(self, texts: list[str], **kwargs: Any) -> EmbeddingResult:
        model = kwargs.pop("model", self.model)
        kwargs.pop("metadata", None)
        if (
            self.embedding_dimension is not None
            and "dimensions" not in kwargs
            and _supports_embedding_dimensions(model)
        ):
            kwargs["dimensions"] = self.embedding_dimension
        response = await _logged(
            provider=self.provider_name,
            role="embeddings",
            operation="create_embeddings",
            call=lambda: self._client.embeddings.create(model=model, input=texts, **kwargs),
        )
        embeddings = _embeddings_from_response(response, expected_count=len(texts))
        if self.embedding_dimension is not None:
            _validate_embedding_dimensions(embeddings, expected_dimension=self.embedding_dimension)
        return EmbeddingResult(
            provider=self.provider_name,
            model=model,
            embeddings=embeddings,
            metadata=_embedding_metadata(response),
        )


class OpenAIJudgeProvider(JudgeEvaluationProvider):
    provider_name = "openai-judge"

    def __init__(self, *, api_key: str, model: str, client: Any | None = None) -> None:
        self.model = model
        self._client = client or _client(api_key)

    async def judge_response(
        self, payload: dict[str, Any], rubric: dict[str, Any], **kwargs: Any
    ) -> JudgeResult:
        strict_schema = _rubric_judge_schema(rubric)
        text_format = _build_strict_text_format(
            schema=strict_schema,
            name="judge_response",
            provider=self.provider_name,
            role="judge",
            operation="judge_response",
        )
        text_kwargs = (
            {"format": text_format} if text_format is not None else {"format": {"type": "json_object"}}
        )
        response = await _logged(
            provider=self.provider_name,
            role="judge",
            operation="judge_response",
            call=lambda: self._client.responses.create(
                model=kwargs.pop("model", self.model),
                input=_judge_prompt(payload, rubric),
                text=text_kwargs,
                **kwargs,
            ),
        )
        data = _json_from_response(response)
        return JudgeResult.from_provider_data(
            provider=self.provider_name,
            model=self.model,
            data=data,
            passing_score=float(rubric.get("passing_score", 1)),
        )


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


def _vision_prompt(prompt: str | None) -> str:
    base_prompt = prompt.strip() if prompt else _VISION_PROMPT
    return (
        f"{base_prompt}\n"
        "Return only valid JSON with this structure: "
        '{"description": string, "candidates": ['
        '{"scientific_name": string, "common_name": string | null, '
        '"confidence_label": "high" | "medium" | "low" | "inconclusive", '
        '"confidence_score": number | null, "visible_traits": string[]}]}'
    )


def _search_prompt(query: str, allowed_domains: Any) -> str:
    prompt = (
        "Search the web for reliable botanical care or taxonomy sources. "
        "Prefer primary, institutional, or persistent reference pages. "
        f"Query: {query}"
    )
    domains = _string_list(allowed_domains)
    if domains:
        prompt += "\nPrefer results from these allowed domains: " + ", ".join(domains)
    return prompt


def _search_results_from_response(response: Any) -> list[SearchResult]:
    text = getattr(response, "output_text", "")
    if not isinstance(text, str):
        text = ""
    results: list[SearchResult] = []
    seen_urls: set[str] = set()
    has_annotations = False
    for annotation in _response_annotations(response):
        if _annotation_value(annotation, "type") != "url_citation":
            continue
        has_annotations = True
        url = str(_annotation_value(annotation, "url") or "").strip()
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc or url in seen_urls:
            continue
        seen_urls.add(url)
        title = str(_annotation_value(annotation, "title") or parsed.netloc).strip()
        snippet = _citation_snippet(annotation, text) or title
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


def _embeddings_from_response(response: Any, *, expected_count: int) -> list[list[float]]:
    data = _iter_any(getattr(response, "data", None))
    if len(data) != expected_count:
        raise OpenAIProviderError(
            f"OpenAI embedding response returned {len(data)} items for {expected_count} inputs"
        )
    ordered = sorted(data, key=lambda item: _embedding_index(item))
    embeddings = [_embedding_vector(item) for item in ordered]
    if sorted(_embedding_index(item) for item in ordered) != list(range(expected_count)):
        raise OpenAIProviderError("OpenAI embedding response indexes did not match input order")
    return embeddings


def _supports_embedding_dimensions(model: str) -> bool:
    return model.startswith("text-embedding-3")


def _validate_embedding_dimensions(
    embeddings: list[list[float]], *, expected_dimension: int
) -> None:
    for index, embedding in enumerate(embeddings):
        if len(embedding) != expected_dimension:
            raise OpenAIProviderError(
                "OpenAI embedding response dimension mismatch: "
                f"expected {expected_dimension}, got {len(embedding)} at index {index}"
            )


def _embedding_index(item: Any) -> int:
    index = _value(item, "index")
    if not isinstance(index, int):
        raise OpenAIProviderError("OpenAI embedding response item was missing an integer index")
    return index


def _embedding_vector(item: Any) -> list[float]:
    embedding = _value(item, "embedding")
    if not isinstance(embedding, list) or not embedding:
        raise OpenAIProviderError("OpenAI embedding response item was missing an embedding vector")
    if not all(isinstance(value, int | float) for value in embedding):
        raise OpenAIProviderError("OpenAI embedding response vector contained non-numeric values")
    return [float(value) for value in embedding]


def _embedding_metadata(response: Any) -> dict[str, Any]:
    usage = getattr(response, "usage", None)
    total_tokens = _value(usage, "total_tokens") if usage is not None else None
    prompt_tokens = _value(usage, "prompt_tokens") if usage is not None else None
    return {
        key: value
        for key, value in {
            "total_tokens": total_tokens,
            "prompt_tokens": prompt_tokens,
        }.items()
        if isinstance(value, int)
    }


def _response_annotations(response: Any) -> list[Any]:
    annotations: list[Any] = []
    for output in _iter_any(getattr(response, "output", None)):
        for content in _iter_any(_value(output, "content")):
            annotations.extend(_iter_any(_value(content, "annotations")))
    return annotations


def _citation_snippet(annotation: Any, text: str) -> str:
    start = _annotation_value(annotation, "start_index")
    end = _annotation_value(annotation, "end_index")
    if isinstance(start, int) and isinstance(end, int) and 0 <= start < end <= len(text):
        return text[start:end].strip()
    return text.strip()


def _annotation_value(annotation: Any, key: str) -> Any:
    return _value(annotation, key)


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


_VISION_PROMPT = """
Analyze this plant image. Return JSON with description and candidates. Each candidate must include
scientific_name, common_name, confidence_label, confidence_score and visible_traits.
""".strip()


_JUDGE_DEFAULT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "status": {
            "type": "string",
            "enum": ["full", "partial", "insufficient", "contradictory"],
            "description": "Answerability status assigned by the judge.",
        },
        "covered_aspects": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Requested domain-qualified aspects directly supported by evidence.",
        },
        "missing_aspects": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Requested domain-qualified aspects not directly supported by evidence.",
        },
        "source_support": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "claim": {
                        "type": "string",
                        "description": "Specific claim that the evidence supports.",
                    },
                    "source_urls": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Source URLs that support the claim.",
                    },
                    "covered_aspects": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Aspects supported by this claim.",
                    },
                    "evidence_quote": {
                        "type": ["string", "null"],
                        "description": "Verbatim evidence supporting the claim, or null.",
                    },
                    "confidence": {
                        "type": ["number", "null"],
                        "description": "Confidence score for this claim, or null.",
                    },
                },
                "required": [
                    "claim",
                    "source_urls",
                    "covered_aspects",
                    "evidence_quote",
                    "confidence",
                ],
                "additionalProperties": False,
            },
            "description": "Per-claim source support evidence.",
        },
        "contradictions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "claim_a": {
                        "type": "string",
                        "description": "First conflicting claim.",
                    },
                    "claim_b": {
                        "type": "string",
                        "description": "Second conflicting claim.",
                    },
                    "source_a_urls": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Source URLs supporting claim_a.",
                    },
                    "source_b_urls": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Source URLs supporting claim_b.",
                    },
                },
                "required": ["claim_a", "claim_b", "source_a_urls", "source_b_urls"],
                "additionalProperties": False,
            },
            "description": "Contradictory claims detected across sources.",
        },
        "confidence": {
            "type": "number",
            "description": "Numeric confidence score between 0 and 1.",
        },
        "score": {
            "type": "number",
            "description": "Numeric score kept aligned with confidence for compatibility.",
        },
        "passed": {
            "type": "boolean",
            "description": "True only when status is full.",
        },
        "reasons": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Short explanations for the status decision.",
        },
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
    "additionalProperties": False,
}


def _rubric_judge_schema(rubric: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(rubric, dict):
        return _JUDGE_DEFAULT_SCHEMA
    explicit = rubric.get("output_schema") or rubric.get("response_schema")
    if isinstance(explicit, dict):
        return explicit
    return _JUDGE_DEFAULT_SCHEMA


_VISION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "description": {
            "type": "string",
            "description": "Concise textual description of the plant image.",
        },
        "candidates": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "scientific_name": {
                        "type": "string",
                        "description": "Scientific name of the candidate plant.",
                    },
                    "common_name": {
                        "type": ["string", "null"],
                        "description": "Common name of the candidate plant, or null when unknown.",
                    },
                    "confidence_label": {
                        "type": "string",
                        "enum": ["high", "medium", "low", "inconclusive"],
                        "description": "Confidence bucket for this candidate.",
                    },
                    "confidence_score": {
                        "type": ["number", "null"],
                        "description": "Numeric confidence score, or null when unavailable.",
                    },
                    "visible_traits": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Visible plant traits supporting the candidate.",
                    },
                },
                "required": [
                    "scientific_name",
                    "common_name",
                    "confidence_label",
                    "confidence_score",
                    "visible_traits",
                ],
                "additionalProperties": False,
            },
            "description": "Ranked list of candidate plant identifications.",
        },
    },
    "required": ["description", "candidates"],
    "additionalProperties": False,
}
