import types

import pytest

from app.core.settings import get_settings
from app.providers.factory import get_provider_registry
from app.providers.gemini import (
    GeminiModelProvider,
    GeminiProviderError,
    GeminiSearchProvider,
)
from app.providers.openai import (
    OpenAIEmbeddingProvider,
    OpenAIJudgeProvider,
    OpenAIModelProvider,
    OpenAISearchProvider,
    OpenAIVisionProvider,
)
from app.providers.types import SearchResult


@pytest.mark.asyncio
async def test_gemini_search_filters_malformed_and_duplicate_citations(
    fake_gemini_module: None,
) -> None:
    class FakeModels:
        async def generate_content(self, **kwargs: object) -> object:
            return types.SimpleNamespace(
                text="Grounded answer.",
                candidates=[
                    types.SimpleNamespace(
                        grounding_metadata={
                            "grounding_chunks": [
                                {"web": {"uri": "not-a-url", "title": "Bad URL"}},
                                {"web": {"uri": "https://example.org/a", "title": "First"}},
                                {"web": {"uri": "https://example.org/a", "title": "Duplicate"}},
                            ],
                            "grounding_supports": [],
                        }
                    )
                ],
            )

    provider = GeminiSearchProvider(
        api_key="test-key",
        model="gemini-2.5-flash",
        client=types.SimpleNamespace(aio=types.SimpleNamespace(models=FakeModels())),
    )

    results = await provider.search("care")

    assert results == [
        SearchResult(
            title="First",
            url="https://example.org/a",
            snippet="First",
            source_domain="example.org",
            metadata={"snippet_source": "title_fallback"},
        )
    ]

@pytest.mark.asyncio
async def test_gemini_search_returns_empty_when_no_valid_citations(
    fake_gemini_module: None,
) -> None:
    class FakeModels:
        async def generate_content(self, **kwargs: object) -> object:
            return types.SimpleNamespace(
                text="Grounded answer without usable URLs.",
                candidates=[
                    types.SimpleNamespace(
                        grounding_metadata=types.SimpleNamespace(
                            grounding_chunks=[types.SimpleNamespace(web=types.SimpleNamespace(uri=""))],
                            grounding_supports=[],
                        )
                    )
                ],
            )

    provider = GeminiSearchProvider(
        api_key="test-key",
        model="gemini-2.5-flash",
        client=types.SimpleNamespace(aio=types.SimpleNamespace(models=FakeModels())),
    )

    assert await provider.search("care") == []

@pytest.mark.asyncio
async def test_gemini_search_rejects_ungrounded_response(
    fake_gemini_module: None,
) -> None:
    class FakeModels:
        async def generate_content(self, **kwargs: object) -> object:
            return types.SimpleNamespace(text="Ungrounded answer.")

    provider = GeminiSearchProvider(
        api_key="test-key",
        model="gemini-2.5-flash",
        client=types.SimpleNamespace(aio=types.SimpleNamespace(models=FakeModels())),
    )

    with pytest.raises(GeminiProviderError, match="grounding metadata was unavailable"):
        await provider.search("care")

@pytest.mark.asyncio
async def test_gemini_provider_errors_wrap_sdk_failures(fake_gemini_module: None) -> None:
    class FakeModels:
        async def generate_content(self, **kwargs: object) -> object:
            raise RuntimeError("sdk failure")

    provider = GeminiModelProvider(
        api_key="test-key",
        model="gemini-2.5-flash",
        client=types.SimpleNamespace(aio=types.SimpleNamespace(models=FakeModels())),
    )

    with pytest.raises(GeminiProviderError, match="Gemini generate_text call failed"):
        await provider.generate_text("care prompt")

@pytest.mark.asyncio
async def test_gemini_provider_call_logging_metadata_is_sanitized(
    monkeypatch: pytest.MonkeyPatch,
    fake_gemini_module: None,
) -> None:
    logged: dict[str, object] = {}

    async def fake_log_provider_call(
        provider: str,
        operation: str,
        call: object,
        *,
        role: str | None = None,
    ) -> object:
        logged.update({"provider": provider, "operation": operation, "role": role})
        return await call()

    class FakeModels:
        async def generate_content(self, **kwargs: object) -> object:
            return types.SimpleNamespace(text="Gemini answer")

    monkeypatch.setattr("app.providers.gemini._client.log_provider_call", fake_log_provider_call)
    provider = GeminiModelProvider(
        api_key="test-key",
        model="gemini-2.5-flash",
        client=types.SimpleNamespace(aio=types.SimpleNamespace(models=FakeModels())),
    )

    await provider.generate_text("care prompt")

    assert logged == {
        "provider": "gemini-model",
        "operation": "generate_text",
        "role": "model",
    }
    assert "test-key" not in str(logged)

@pytest.mark.asyncio
async def test_openai_embedding_provider_call_logging_metadata_is_sanitized(
    monkeypatch: pytest.MonkeyPatch,
    fake_openai_module: None,
) -> None:
    logged: dict[str, object] = {}

    async def fake_log_provider_call(
        provider: str,
        operation: str,
        call: object,
        *,
        role: str | None = None,
    ) -> object:
        logged.update({"provider": provider, "operation": operation, "role": role})
        return await call()

    class FakeEmbeddings:
        async def create(self, **kwargs: object) -> object:
            return types.SimpleNamespace(data=[types.SimpleNamespace(index=0, embedding=[1.0])])

    monkeypatch.setattr("app.providers.openai._client.log_provider_call", fake_log_provider_call)
    provider = OpenAIEmbeddingProvider(api_key="test-key", model="text-embedding-3-small")
    provider._client = types.SimpleNamespace(embeddings=FakeEmbeddings())

    await provider.create_embeddings(["first"])

    assert logged == {
        "provider": "openai-embedding",
        "operation": "create_embeddings",
        "role": "embeddings",
    }
    assert "test-key" not in str(logged)

@pytest.mark.asyncio
async def test_openai_search_parses_url_citation_annotations(
    fake_openai_module: None,
) -> None:
    class FakeResponses:
        def __init__(self) -> None:
            self.kwargs: dict[str, object] | None = None

        async def create(self, **kwargs: object) -> object:
            self.kwargs = kwargs
            text = "Kew bear paw succulent profile. Invalid citation."
            return types.SimpleNamespace(
                output_text=text,
                output=[
                    types.SimpleNamespace(
                        content=[
                            types.SimpleNamespace(
                                annotations=[
                                    types.SimpleNamespace(
                                        type="url_citation",
                                        title="Kew Plants of the World Online",
                                        url="https://powo.science.kew.org/taxon/example",
                                        start_index=0,
                                        end_index=32,
                                    ),
                                    {
                                        "type": "url_citation",
                                        "title": "No URL",
                                        "url": "",
                                    },
                                ]
                            )
                        ]
                    )
                ],
            )

    responses = FakeResponses()
    provider = OpenAISearchProvider(api_key="test-key", model="gpt-4.1-mini")
    provider._client = types.SimpleNamespace(responses=responses)

    results = await provider.search(
        "Cotyledon tomentosa care",
        allowed_domains=["powo.science.kew.org"],
        temperature=0,
    )

    assert responses.kwargs is not None
    assert responses.kwargs["model"] == "gpt-4.1-mini"
    assert responses.kwargs["tools"] == [{"type": "web_search"}]
    assert "powo.science.kew.org" in str(responses.kwargs["input"])
    assert results[0].title == "Kew Plants of the World Online"
    assert results[0].url == "https://powo.science.kew.org/taxon/example"
    assert results[0].snippet == "Kew bear paw succulent profile."
    assert results[0].source_domain == "powo.science.kew.org"
    assert len(results) == 1


# ---------------------------------------------------------------------------
# Classifier model wiring through the factory
# ---------------------------------------------------------------------------

def test_factory_wires_openai_classifier_model(
    monkeypatch: pytest.MonkeyPatch,
    fake_openai_module: None,
) -> None:
    monkeypatch.setenv("MODEL_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_TEXT_MODEL", "gpt-text")
    monkeypatch.setenv("OPENAI_CLASSIFIER_MODEL", "gpt-classifier")
    get_settings.cache_clear()

    providers = get_provider_registry()

    assert isinstance(providers.model, OpenAIModelProvider)
    assert providers.model.model == "gpt-text"
    assert providers.model.classifier_model == "gpt-classifier"

def test_factory_wires_gemini_classifier_model(
    monkeypatch: pytest.MonkeyPatch,
    fake_gemini_module: None,
) -> None:
    monkeypatch.setenv("MODEL_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_TEXT_MODEL", "gemini-text")
    monkeypatch.setenv("GEMINI_CLASSIFIER_MODEL", "gemini-classifier")
    get_settings.cache_clear()

    providers = get_provider_registry()

    assert isinstance(providers.model, GeminiModelProvider)
    assert providers.model.model == "gemini-text"
    assert providers.model.classifier_model == "gemini-classifier"

def test_factory_wires_classifier_model_for_each_provider_in_chain(
    monkeypatch: pytest.MonkeyPatch,
    fake_gemini_module: None,
    fake_openai_module: None,
) -> None:
    monkeypatch.setenv("MODEL_PROVIDERS", '["gemini", "openai"]')
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai")
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini")
    monkeypatch.setenv("GEMINI_TEXT_MODEL", "gemini-text")
    monkeypatch.setenv("GEMINI_CLASSIFIER_MODEL", "gemini-classifier")
    monkeypatch.setenv("OPENAI_TEXT_MODEL", "openai-text")
    monkeypatch.setenv("OPENAI_CLASSIFIER_MODEL", "openai-classifier")
    get_settings.cache_clear()

    providers = get_provider_registry()

    from app.providers.wrappers import ModelProviderFallbackWrapper
    assert isinstance(providers.model, ModelProviderFallbackWrapper)
    chain = providers.model._providers
    assert len(chain) == 2
    assert isinstance(chain[0], GeminiModelProvider)
    assert chain[0].classifier_model == "gemini-classifier"
    assert isinstance(chain[1], OpenAIModelProvider)
    assert chain[1].classifier_model == "openai-classifier"

@pytest.mark.asyncio
async def test_openai_classifier_purpose_routes_to_classifier_model(
    fake_openai_module: None,
) -> None:
    class FakeResponses:
        def __init__(self) -> None:
            self.kwargs: dict[str, object] | None = None

        async def create(self, **kwargs: object) -> object:
            self.kwargs = kwargs
            return types.SimpleNamespace(output_text='{"ok": true}')

    responses = FakeResponses()
    provider = OpenAIModelProvider(
        api_key="test-key",
        model="gpt-text",
        classifier_model="gpt-classifier",
    )
    provider._client = types.SimpleNamespace(responses=responses)

    result = await provider.generate_json(
        "classifier prompt", {"type": "object"}, model_purpose="classifier"
    )

    assert responses.kwargs is not None
    assert responses.kwargs["model"] == "gpt-classifier"
    assert result.model == "gpt-classifier"

@pytest.mark.asyncio
async def test_openai_default_text_call_does_not_use_classifier_model(
    fake_openai_module: None,
) -> None:
    class FakeResponses:
        def __init__(self) -> None:
            self.kwargs: dict[str, object] | None = None

        async def create(self, **kwargs: object) -> object:
            self.kwargs = kwargs
            return types.SimpleNamespace(output_text="text answer")

    responses = FakeResponses()
    provider = OpenAIModelProvider(
        api_key="test-key",
        model="gpt-text",
        classifier_model="gpt-classifier",
    )
    provider._client = types.SimpleNamespace(responses=responses)

    result = await provider.generate_text("text prompt")

    assert responses.kwargs is not None
    assert responses.kwargs["model"] == "gpt-text"
    assert result.model == "gpt-text"

@pytest.mark.asyncio
async def test_openai_explicit_model_override_wins_over_classifier_purpose(
    fake_openai_module: None,
) -> None:
    class FakeResponses:
        def __init__(self) -> None:
            self.kwargs: dict[str, object] | None = None

        async def create(self, **kwargs: object) -> object:
            self.kwargs = kwargs
            return types.SimpleNamespace(output_text='{"ok": true}')

    responses = FakeResponses()
    provider = OpenAIModelProvider(
        api_key="test-key",
        model="gpt-text",
        classifier_model="gpt-classifier",
    )
    provider._client = types.SimpleNamespace(responses=responses)

    result = await provider.generate_json(
        "prompt",
        {"type": "object"},
        model="gpt-experimental",
        model_purpose="classifier",
    )

    assert responses.kwargs is not None
    assert responses.kwargs["model"] == "gpt-experimental"
    assert result.model == "gpt-experimental"

@pytest.mark.asyncio
async def test_gemini_classifier_purpose_routes_to_classifier_model(
    fake_gemini_module: None,
) -> None:
    class FakeModels:
        def __init__(self) -> None:
            self.kwargs: dict[str, object] | None = None

        async def generate_content(self, **kwargs: object) -> object:
            self.kwargs = kwargs
            return types.SimpleNamespace(text='{"ok": true}')

    models = FakeModels()
    provider = GeminiModelProvider(
        api_key="test-key",
        model="gemini-text",
        classifier_model="gemini-classifier",
        client=types.SimpleNamespace(aio=types.SimpleNamespace(models=models)),
    )

    result = await provider.generate_json(
        "classifier prompt", {"type": "object"}, model_purpose="classifier"
    )

    assert models.kwargs is not None
    assert models.kwargs["model"] == "gemini-classifier"
    assert result.model == "gemini-classifier"

@pytest.mark.asyncio
async def test_gemini_default_text_call_does_not_use_classifier_model(
    fake_gemini_module: None,
) -> None:
    class FakeModels:
        def __init__(self) -> None:
            self.kwargs: dict[str, object] | None = None

        async def generate_content(self, **kwargs: object) -> object:
            self.kwargs = kwargs
            return types.SimpleNamespace(text="text answer")

    models = FakeModels()
    provider = GeminiModelProvider(
        api_key="test-key",
        model="gemini-text",
        classifier_model="gemini-classifier",
        client=types.SimpleNamespace(aio=types.SimpleNamespace(models=models)),
    )

    result = await provider.generate_text("text prompt")

    assert models.kwargs is not None
    assert models.kwargs["model"] == "gemini-text"
    assert result.model == "gemini-text"

@pytest.mark.asyncio
async def test_openai_classifier_purpose_does_not_forward_model_purpose_to_sdk(
    fake_openai_module: None,
) -> None:
    """The OpenAI SDK must not receive `model_purpose` as an unknown argument."""
    seen: list[dict[str, object]] = []

    class FakeResponses:
        async def create(self, **kwargs: object) -> object:
            seen.append(dict(kwargs))
            return types.SimpleNamespace(output_text='{"ok": true}')

    provider = OpenAIModelProvider(
        api_key="test-key",
        model="gpt-text",
        classifier_model="gpt-classifier",
    )
    provider._client = types.SimpleNamespace(responses=FakeResponses())

    await provider.generate_json(
        "classifier prompt", {"type": "object"}, model_purpose="classifier"
    )

    assert seen, "SDK should have been called"
    assert "model_purpose" not in seen[0], (
        f"model_purpose leaked to OpenAI SDK: kwargs={seen[0]!r}"
    )

@pytest.mark.asyncio
async def test_gemini_classifier_purpose_does_not_forward_model_purpose_to_sdk(
    fake_gemini_module: None,
) -> None:
    """The Gemini SDK must not receive `model_purpose` as an unknown argument."""
    seen: list[dict[str, object]] = []

    class FakeModels:
        async def generate_content(self, **kwargs: object) -> object:
            seen.append(dict(kwargs))
            return types.SimpleNamespace(text='{"ok": true}')

    models = FakeModels()
    provider = GeminiModelProvider(
        api_key="test-key",
        model="gemini-text",
        classifier_model="gemini-classifier",
        client=types.SimpleNamespace(aio=types.SimpleNamespace(models=models)),
    )

    await provider.generate_json(
        "classifier prompt", {"type": "object"}, model_purpose="classifier"
    )

    assert seen, "SDK should have been called"
    assert "model_purpose" not in seen[0], (
        f"model_purpose leaked to Gemini SDK: kwargs={seen[0]!r}"
    )


# ---------------------------------------------------------------------------
# OpenAI strict JSON schema (json_schema) wiring for generate_json / vision /
# judge. The provider must send `text.format.type = "json_schema"` with
# `strict: true` and `additionalProperties: false` when the supplied schema is
# safe, and fall back to JSON object mode with provider_json_schema_fallback
# diagnostics when it is not.
# ---------------------------------------------------------------------------

def test_openai_to_strict_schema_marks_all_properties_required_and_disallows_extras() -> None:
    from app.providers.openai import _to_openai_strict_schema

    sanitized = _to_openai_strict_schema(
        {
            "type": "object",
            "properties": {
                "intent": {"type": "string", "enum": ["a", "b"]},
                "topic": {"type": "string", "description": "topic"},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "plant_reference": {"type": ["string", "null"]},
            },
        }
    )

    assert sanitized is not None
    assert sanitized["additionalProperties"] is False
    assert set(sanitized["required"]) == {
        "intent",
        "topic",
        "confidence",
        "plant_reference",
    }
    assert sanitized["properties"]["intent"]["enum"] == ["a", "b"]
    assert sanitized["properties"]["plant_reference"]["type"] == ["string", "null"]
    assert sanitized["properties"]["confidence"]["minimum"] == 0
    assert sanitized["properties"]["topic"]["description"] == "topic"

def test_openai_to_strict_schema_returns_none_for_unsupported_constructs() -> None:
    from app.providers.openai import _to_openai_strict_schema

    assert _to_openai_strict_schema({"$ref": "#/definitions/thing"}) is None
    assert _to_openai_strict_schema(
        {"type": "object", "properties": {"x": {"oneOf": [{"type": "string"}]}}}
    ) is None
    assert _to_openai_strict_schema(
        {"type": "object", "properties": {"x": {"allOf": [{"type": "string"}]}}}
    ) is None
    assert _to_openai_strict_schema(
        {"type": "object", "properties": {"x": {"type": "object"}, "y": {}}}
    ) is None

@pytest.mark.asyncio
async def test_openai_generate_json_uses_strict_json_schema_format(
    fake_openai_module: None,
) -> None:
    class FakeResponses:
        def __init__(self) -> None:
            self.kwargs: dict[str, object] | None = None

        async def create(self, **kwargs: object) -> object:
            self.kwargs = kwargs
            return types.SimpleNamespace(
                output_text=(
                    '{"language":"es","answer_language":"es","intent":"plant_care_question",'
                    '"topic":"watering","required_aspects":["watering_frequency_or_trigger"],'
                    '"plant_reference":"Pata","confidence":0.9,"needs_retrieval":true}'
                )
            )

    responses = FakeResponses()
    provider = OpenAIModelProvider(
        api_key="test-key",
        model="gpt-text",
        classifier_model="gpt-classifier",
    )
    provider._client = types.SimpleNamespace(responses=responses)

    schema = {
        "type": "object",
        "properties": {
            "language": {"type": "string"},
            "answer_language": {"type": "string"},
            "intent": {"type": "string", "enum": ["plant_care_question"]},
            "topic": {"type": "string"},
            "required_aspects": {"type": "array", "items": {"type": "string"}},
            "plant_reference": {"type": ["string", "null"]},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "needs_retrieval": {"type": "boolean"},
        },
    }

    await provider.generate_json(
        "classifier prompt", schema, model_purpose="classifier"
    )

    assert responses.kwargs is not None
    text = responses.kwargs["text"]
    assert isinstance(text, dict)
    text_format = text["format"]
    assert text_format["type"] == "json_schema"
    assert text_format["strict"] is True
    assert text_format["schema"]["additionalProperties"] is False
    assert set(text_format["schema"]["required"]) == set(schema["properties"].keys())

@pytest.mark.asyncio
async def test_openai_generate_json_falls_back_to_json_object_mode(
    fake_openai_module: None,
) -> None:
    """When the schema cannot be safely sanitized, the provider MUST fall back
    to JSON object mode and emit a `provider_json_schema_fallback` diagnostic
    without logging raw secrets."""

    class FakeResponses:
        def __init__(self) -> None:
            self.kwargs: dict[str, object] | None = None

        async def create(self, **kwargs: object) -> object:
            self.kwargs = kwargs
            return types.SimpleNamespace(output_text='{"ok": true}')

    responses = FakeResponses()
    provider = OpenAIModelProvider(api_key="test-key", model="gpt-text")
    provider._client = types.SimpleNamespace(responses=responses)

    unsupported_schema = {
        "type": "object",
        "properties": {"x": {"oneOf": [{"type": "string"}, {"type": "number"}]}},
    }

    fallback_calls: list[dict[str, object]] = []

    class _StubLogger:
        def info(self, message: str, *args: object, **kwargs: object) -> None:
            fallback_calls.append({"message": message, **kwargs})

    monkey = pytest.MonkeyPatch()
    try:
        monkey.setattr("app.providers.openai.strict_format.logger", _StubLogger())
        await provider.generate_json(
            "prompt", unsupported_schema, model_purpose="classifier"
        )
    finally:
        monkey.undo()

    assert responses.kwargs is not None
    text_format = responses.kwargs["text"]["format"]
    assert text_format == {"type": "json_object"}
    assert fallback_calls, "provider_json_schema_fallback diagnostic should be emitted"
    diagnostic = fallback_calls[0]
    extras = diagnostic.get("extra") or {}
    assert extras.get("ctx_event") == "provider_json_schema_fallback"
    assert extras.get("ctx_provider") == "openai-model"
    assert extras.get("ctx_role") == "model"
    assert extras.get("ctx_operation") == "generate_json"
    assert "test-key" not in str(diagnostic)

@pytest.mark.asyncio
async def test_openai_vision_uses_strict_json_schema_format(
    fake_openai_module: None,
) -> None:
    class FakeResponses:
        def __init__(self) -> None:
            self.kwargs: dict[str, object] | None = None

        async def create(self, **kwargs: object) -> object:
            self.kwargs = kwargs
            return types.SimpleNamespace(
                output_text=(
                    '{"description":"green leaves","candidates":['
                    '{"scientific_name":"Pilea peperomioides","common_name":null,'
                    '"confidence_label":"medium","confidence_score":0.7,'
                    '"visible_traits":["round leaves"]}]}'
                )
            )

    responses = FakeResponses()
    provider = OpenAIVisionProvider(api_key="test-key", model="gpt-vision")
    provider._client = types.SimpleNamespace(responses=responses)

    await provider.analyze_image(b"png-bytes", prompt="Analyze this plant.")

    assert responses.kwargs is not None
    text_format = responses.kwargs["text"]["format"]
    assert text_format["type"] == "json_schema"
    assert text_format["strict"] is True
    assert text_format["schema"]["additionalProperties"] is False
    assert set(text_format["schema"]["required"]) == {"description", "candidates"}
    candidates_schema = text_format["schema"]["properties"]["candidates"]["items"]
    assert candidates_schema["additionalProperties"] is False
    assert "scientific_name" in candidates_schema["required"]

@pytest.mark.asyncio
async def test_openai_judge_uses_strict_json_schema_format(
    fake_openai_module: None,
) -> None:
    class FakeResponses:
        def __init__(self) -> None:
            self.kwargs: dict[str, object] | None = None

        async def create(self, **kwargs: object) -> object:
            self.kwargs = kwargs
            return types.SimpleNamespace(
                output_text=(
                    '{"status":"full","covered_aspects":["watering_frequency_or_trigger"],'
                    '"missing_aspects":[],"source_support":[],'
                    '"contradictions":[],"confidence":0.9,"score":0.9,'
                    '"passed":true,"reasons":[]}'
                )
            )

    responses = FakeResponses()
    provider = OpenAIJudgeProvider(api_key="test-key", model="gpt-judge")
    provider._client = types.SimpleNamespace(responses=responses)

    await provider.judge_response({"answer": "x"}, {"passing_score": 0.8})

    assert responses.kwargs is not None
    text_format = responses.kwargs["text"]["format"]
    assert text_format["type"] == "json_schema"
    assert text_format["strict"] is True
    assert text_format["schema"]["additionalProperties"] is False
    for required_field in (
        "status",
        "covered_aspects",
        "missing_aspects",
        "source_support",
        "contradictions",
        "confidence",
        "score",
        "passed",
        "reasons",
    ):
        assert required_field in text_format["schema"]["required"]

@pytest.mark.asyncio
async def test_openai_judge_falls_back_to_json_object_mode_for_unsupported_rubric(
    fake_openai_module: None,
) -> None:
    """When the rubric exposes a schema with unsupported constructs, the judge
    provider MUST fall back to JSON object mode and emit the fallback diagnostic."""

    class FakeResponses:
        def __init__(self) -> None:
            self.kwargs: dict[str, object] | None = None

        async def create(self, **kwargs: object) -> object:
            self.kwargs = kwargs
            return types.SimpleNamespace(output_text='{"ok": true}')

    responses = FakeResponses()
    provider = OpenAIJudgeProvider(api_key="test-key", model="gpt-judge")
    provider._client = types.SimpleNamespace(responses=responses)

    fallback_calls: list[dict[str, object]] = []

    class _StubLogger:
        def info(self, message: str, *args: object, **kwargs: object) -> None:
            fallback_calls.append({"message": message, **kwargs})

    monkey = pytest.MonkeyPatch()
    try:
        monkey.setattr("app.providers.openai.strict_format.logger", _StubLogger())
        await provider.judge_response(
            {"answer": "x"},
            {
                "passing_score": 0.8,
                "output_schema": {
                    "type": "object",
                    "properties": {
                        "x": {"oneOf": [{"type": "string"}, {"type": "number"}]}
                    },
                },
            },
        )
    finally:
        monkey.undo()

    assert responses.kwargs is not None
    assert responses.kwargs["text"]["format"] == {"type": "json_object"}
    assert fallback_calls
    diagnostic = fallback_calls[0]
    extras = diagnostic.get("extra") or {}
    assert extras.get("ctx_event") == "provider_json_schema_fallback"
    assert extras.get("ctx_operation") == "judge_response"
    assert "test-key" not in str(diagnostic)

