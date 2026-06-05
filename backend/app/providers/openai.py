import base64
import json
from collections.abc import Awaitable, Callable
from typing import Any
from urllib.parse import urlparse

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


class OpenAIModelProvider(ModelProvider):
    provider_name = "openai-model"

    def __init__(self, *, api_key: str, model: str) -> None:
        self.model = model
        self._client = _client(api_key)

    async def generate_text(self, prompt: str, **kwargs: Any) -> TextGenerationResult:
        response = await _logged(
            provider=self.provider_name,
            role="model",
            operation="generate_text",
            call=lambda: self._client.responses.create(
                model=kwargs.pop("model", self.model),
                input=prompt,
                **kwargs,
            ),
        )
        return TextGenerationResult(
            provider=self.provider_name,
            model=self.model,
            text=_response_text(response),
        )

    async def generate_json(
        self, prompt: str, schema: dict[str, Any], **kwargs: Any
    ) -> JsonGenerationResult:
        response = await _logged(
            provider=self.provider_name,
            role="model",
            operation="generate_json",
            call=lambda: self._client.responses.create(
                model=kwargs.pop("model", self.model),
                input=prompt,
                text={"format": {"type": "json_object"}},
                **kwargs,
            ),
        )
        return JsonGenerationResult(
            provider=self.provider_name,
            model=self.model,
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
                text={"format": {"type": "json_object"}},
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
        response = await _logged(
            provider=self.provider_name,
            role="judge",
            operation="judge_response",
            call=lambda: self._client.responses.create(
                model=kwargs.pop("model", self.model),
                input=_judge_prompt(payload, rubric),
                text={"format": {"type": "json_object"}},
                **kwargs,
            ),
        )
        data = _json_from_response(response)
        score = float(data.get("score", 0))
        passed = bool(data.get("passed", score >= float(rubric.get("passing_score", 1))))
        reasons = data.get("reasons") or []
        return JudgeResult(
            provider=self.provider_name,
            model=self.model,
            score=score,
            passed=passed,
            reasons=[str(reason) for reason in reasons],
        )


def _confidence_label(value: Any) -> ConfidenceLabel:
    try:
        return ConfidenceLabel(str(value))
    except ValueError:
        return ConfidenceLabel.inconclusive


def _judge_prompt(payload: dict[str, Any], rubric: dict[str, Any]) -> str:
    return (
        "Evaluate the assistant output against the rubric. "
        "Return JSON with score, passed, and reasons.\n"
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
    for annotation in _response_annotations(response):
        if _annotation_value(annotation, "type") != "url_citation":
            continue
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
