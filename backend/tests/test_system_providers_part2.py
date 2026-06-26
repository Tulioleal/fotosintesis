import types

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.settings import get_settings
from app.main import app
from app.providers.factory import get_provider_registry
from app.providers.gemini import (
    GeminiJudgeProvider,
    GeminiModelProvider,
    GeminiProviderError,
    GeminiSearchProvider,
    GeminiVisionProvider,
    _JUDGE_SCHEMA,
    _VISION_SCHEMA,
)
from app.providers.openai import (
    OpenAIEmbeddingProvider,
    OpenAIProviderError,
    OpenAISearchProvider,
)
from app.providers.types import SearchResult


def test_missing_gemini_credentials_fail_for_selected_judge_role(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("JUDGE_PROVIDER", "gemini")
    get_settings.cache_clear()

    with pytest.raises(
        ValueError, match="GEMINI_API_KEY is required when judge provider is gemini"
    ):
        get_provider_registry()

def test_missing_gemini_credentials_fail_for_selected_search_role(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SEARCH_PROVIDER", "gemini")
    get_settings.cache_clear()

    with pytest.raises(
        ValueError, match="GEMINI_API_KEY is required when search provider is gemini"
    ):
        get_provider_registry()

def test_gemini_is_not_supported_for_embeddings(
    monkeypatch: pytest.MonkeyPatch,
    fake_gemini_module: None,
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    monkeypatch.setenv("EMBEDDING_PROVIDER", "gemini")
    get_settings.cache_clear()

    with pytest.raises(ValueError, match="Unsupported embedding provider: gemini"):
        get_provider_registry()

def test_openai_search_selection_does_not_change_other_providers(
    monkeypatch: pytest.MonkeyPatch,
    fake_openai_module: None,
) -> None:
    monkeypatch.setenv("SEARCH_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    get_settings.cache_clear()

    providers = get_provider_registry()

    assert isinstance(providers.search, OpenAISearchProvider)
    assert providers.model.__class__.__name__ == "MockModelProvider"
    assert providers.vision.__class__.__name__ == "MockVisionPlantIdentificationProvider"
    assert providers.judge.__class__.__name__ == "MockModelProvider"
    assert providers.embeddings.__class__.__name__ == "MockEmbeddingProvider"

def test_openai_embedding_selection_does_not_change_other_providers(
    monkeypatch: pytest.MonkeyPatch,
    fake_openai_module: None,
) -> None:
    monkeypatch.setenv("EMBEDDING_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
    get_settings.cache_clear()

    providers = get_provider_registry()

    assert isinstance(providers.embeddings, OpenAIEmbeddingProvider)
    assert providers.embeddings.model == "text-embedding-3-small"
    assert providers.embeddings.embedding_dimension == 8
    assert providers.model.__class__.__name__ == "MockModelProvider"
    assert providers.vision.__class__.__name__ == "MockVisionPlantIdentificationProvider"
    assert providers.judge.__class__.__name__ == "MockModelProvider"
    assert providers.search.__class__.__name__ == "MockSearchProvider"

def test_missing_openai_credentials_only_fail_selected_openai_roles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MODEL_PROVIDER", "openai")
    get_settings.cache_clear()

    with pytest.raises(
        ValueError, match="OPENAI_API_KEY is required when model provider is openai"
    ):
        get_provider_registry()

    monkeypatch.setenv("MODEL_PROVIDER", "mock")
    get_settings.cache_clear()

    providers = get_provider_registry()
    assert providers.model.__class__.__name__ == "MockModelProvider"

def test_missing_openai_credentials_fail_for_selected_search_role(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SEARCH_PROVIDER", "openai")
    get_settings.cache_clear()

    with pytest.raises(
        ValueError, match="OPENAI_API_KEY is required when search provider is openai"
    ):
        get_provider_registry()

    monkeypatch.setenv("SEARCH_PROVIDER", "mock")
    get_settings.cache_clear()

    providers = get_provider_registry()
    assert providers.search.__class__.__name__ == "MockSearchProvider"

def test_missing_openai_credentials_fail_for_selected_embedding_role(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EMBEDDING_PROVIDER", "openai")
    get_settings.cache_clear()

    with pytest.raises(
        ValueError, match="OPENAI_API_KEY is required when embedding provider is openai"
    ):
        get_provider_registry()

    monkeypatch.setenv("EMBEDDING_PROVIDER", "mock")
    get_settings.cache_clear()

    providers = get_provider_registry()
    assert providers.embeddings.__class__.__name__ == "MockEmbeddingProvider"

@pytest.mark.asyncio
async def test_health_reports_openai_embedding_provider(
    monkeypatch: pytest.MonkeyPatch,
    fake_openai_module: None,
) -> None:
    monkeypatch.setenv("EMBEDDING_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    get_settings.cache_clear()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json()["dependencies"]["embedding_provider"] == "OpenAIEmbeddingProvider"

@pytest.mark.asyncio
async def test_openai_embeddings_map_response_in_input_order(
    fake_openai_module: None,
) -> None:
    class FakeEmbeddings:
        def __init__(self) -> None:
            self.kwargs: dict[str, object] | None = None

        async def create(self, **kwargs: object) -> object:
            self.kwargs = kwargs
            return types.SimpleNamespace(
                data=[
                    types.SimpleNamespace(index=1, embedding=[2, 2.5]),
                    types.SimpleNamespace(index=0, embedding=[1, 1.5]),
                ],
                usage=types.SimpleNamespace(prompt_tokens=7, total_tokens=9),
            )

    embeddings = FakeEmbeddings()
    provider = OpenAIEmbeddingProvider(api_key="test-key", model="text-embedding-3-small")
    provider._client = types.SimpleNamespace(embeddings=embeddings)

    result = await provider.create_embeddings(["first", "second"], dimensions=2)

    assert embeddings.kwargs == {
        "model": "text-embedding-3-small",
        "input": ["first", "second"],
        "dimensions": 2,
    }
    assert result.provider == "openai-embedding"
    assert result.model == "text-embedding-3-small"
    assert result.embeddings == [[1.0, 1.5], [2.0, 2.5]]
    assert result.metadata == {"prompt_tokens": 7, "total_tokens": 9}

@pytest.mark.asyncio
async def test_openai_embeddings_drop_metadata_and_use_configured_dimensions(
    fake_openai_module: None,
) -> None:
    class FakeEmbeddings:
        def __init__(self) -> None:
            self.kwargs: dict[str, object] | None = None

        async def create(self, **kwargs: object) -> object:
            self.kwargs = kwargs
            return types.SimpleNamespace(
                data=[types.SimpleNamespace(index=0, embedding=[0.1] * 8)],
                usage=types.SimpleNamespace(prompt_tokens=1, total_tokens=1),
            )

    embeddings = FakeEmbeddings()
    provider = OpenAIEmbeddingProvider(
        api_key="test-key",
        model="text-embedding-3-small",
        embedding_dimension=8,
    )
    provider._client = types.SimpleNamespace(embeddings=embeddings)

    result = await provider.create_embeddings(
        ["first"],
        metadata=[{"topic": "watering"}],
    )

    assert embeddings.kwargs == {
        "model": "text-embedding-3-small",
        "input": ["first"],
        "dimensions": 8,
    }
    assert len(result.embeddings[0]) == 8

@pytest.mark.asyncio
async def test_openai_embeddings_reject_wrong_configured_dimension(
    fake_openai_module: None,
) -> None:
    class FakeEmbeddings:
        async def create(self, **kwargs: object) -> object:
            return types.SimpleNamespace(
                data=[types.SimpleNamespace(index=0, embedding=[0.1, 0.2, 0.3])],
                usage=types.SimpleNamespace(prompt_tokens=1, total_tokens=1),
            )

    provider = OpenAIEmbeddingProvider(
        api_key="test-key",
        model="text-embedding-3-small",
        embedding_dimension=8,
    )
    provider._client = types.SimpleNamespace(embeddings=FakeEmbeddings())

    with pytest.raises(OpenAIProviderError, match="expected 8, got 3"):
        await provider.create_embeddings(["first"])

@pytest.mark.asyncio
async def test_openai_embeddings_validate_mismatched_response_count(
    fake_openai_module: None,
) -> None:
    class FakeEmbeddings:
        async def create(self, **kwargs: object) -> object:
            return types.SimpleNamespace(data=[types.SimpleNamespace(index=0, embedding=[1.0])])

    provider = OpenAIEmbeddingProvider(api_key="test-key", model="text-embedding-3-small")
    provider._client = types.SimpleNamespace(embeddings=FakeEmbeddings())

    with pytest.raises(OpenAIProviderError, match="returned 1 items for 2 inputs"):
        await provider.create_embeddings(["first", "second"])


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "item,error",
    [
        (types.SimpleNamespace(index="0", embedding=[1.0]), "missing an integer index"),
        (types.SimpleNamespace(index=0, embedding=[]), "missing an embedding vector"),
        (types.SimpleNamespace(index=0, embedding=["secret"]), "contained non-numeric values"),
    ],
)

async def test_openai_embeddings_validate_malformed_items(
    fake_openai_module: None,
    item: object,
    error: str,
) -> None:
    class FakeEmbeddings:
        async def create(self, **kwargs: object) -> object:
            return types.SimpleNamespace(data=[item])

    provider = OpenAIEmbeddingProvider(api_key="test-key", model="text-embedding-3-small")
    provider._client = types.SimpleNamespace(embeddings=FakeEmbeddings())

    with pytest.raises(OpenAIProviderError, match=error):
        await provider.create_embeddings(["first"])

@pytest.mark.asyncio
async def test_gemini_text_generation_maps_response(fake_gemini_module: None) -> None:
    class FakeModels:
        def __init__(self) -> None:
            self.kwargs: dict[str, object] | None = None

        async def generate_content(self, **kwargs: object) -> object:
            self.kwargs = kwargs
            return types.SimpleNamespace(text="Gemini plant care answer")

    models = FakeModels()
    provider = GeminiModelProvider(
        api_key="test-key",
        model="gemini-2.5-flash",
        client=types.SimpleNamespace(aio=types.SimpleNamespace(models=models)),
    )

    result = await provider.generate_text("care prompt", temperature=0)

    assert models.kwargs is not None
    assert models.kwargs["model"] == "gemini-2.5-flash"
    assert models.kwargs["contents"] == "care prompt"
    assert models.kwargs["config"].kwargs == {"temperature": 0}
    assert result.provider == "gemini-model"
    assert result.model == "gemini-2.5-flash"
    assert result.text == "Gemini plant care answer"

@pytest.mark.asyncio
async def test_gemini_json_generation_maps_object_response(fake_gemini_module: None) -> None:
    class FakeModels:
        def __init__(self) -> None:
            self.kwargs: dict[str, object] | None = None

        async def generate_content(self, **kwargs: object) -> object:
            self.kwargs = kwargs
            return types.SimpleNamespace(text='{"answer": "water sparingly"}')

    models = FakeModels()
    provider = GeminiModelProvider(
        api_key="test-key",
        model="gemini-2.5-flash",
        client=types.SimpleNamespace(aio=types.SimpleNamespace(models=models)),
    )

    result = await provider.generate_json("Return care JSON", {"answer": {"type": "string"}})

    assert models.kwargs is not None
    assert models.kwargs["config"].kwargs["response_mime_type"] == "application/json"
    assert models.kwargs["config"].kwargs["response_schema"] == {"answer": {"type": "string"}}
    assert result.provider == "gemini-model"
    assert result.data == {"answer": "water sparingly"}
    assert result.metadata == {"schema_keys": ["answer"]}

@pytest.mark.asyncio
async def test_gemini_json_generation_normalizes_nullable_schema(
    fake_gemini_module: None,
) -> None:
    class FakeModels:
        def __init__(self) -> None:
            self.kwargs: dict[str, object] | None = None

        async def generate_content(self, **kwargs: object) -> object:
            self.kwargs = kwargs
            return types.SimpleNamespace(text='{"plant_reference": null}')

    models = FakeModels()
    provider = GeminiModelProvider(
        api_key="test-key",
        model="gemini-2.5-flash",
        client=types.SimpleNamespace(aio=types.SimpleNamespace(models=models)),
    )
    schema = {
        "type": "object",
        "properties": {"plant_reference": {"type": ["string", "null"]}},
    }

    await provider.generate_json("Return care JSON", schema)

    assert models.kwargs is not None
    assert models.kwargs["config"].kwargs["response_schema"] == {
        "type": "object",
        "properties": {
            "plant_reference": {"type": "string", "nullable": True},
        },
    }
    assert schema["properties"]["plant_reference"]["type"] == ["string", "null"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response,error",
    [
        (types.SimpleNamespace(text="not json"), "not valid JSON"),
        (types.SimpleNamespace(text='["not", "object"]'), "must be an object"),
    ],
)

async def test_gemini_json_generation_rejects_invalid_responses(
    fake_gemini_module: None,
    response: object,
    error: str,
) -> None:
    class FakeModels:
        async def generate_content(self, **kwargs: object) -> object:
            return response

    provider = GeminiModelProvider(
        api_key="test-key",
        model="gemini-2.5-flash",
        client=types.SimpleNamespace(aio=types.SimpleNamespace(models=FakeModels())),
    )

    with pytest.raises(GeminiProviderError, match=error):
        await provider.generate_json("Return care JSON", {})

@pytest.mark.asyncio
async def test_gemini_vision_maps_candidate_response(fake_gemini_module: None) -> None:
    class FakeModels:
        def __init__(self) -> None:
            self.kwargs: dict[str, object] | None = None

        async def generate_content(self, **kwargs: object) -> object:
            self.kwargs = kwargs
            return types.SimpleNamespace(
                parsed={
                    "description": "round green leaves",
                    "candidates": [
                        {
                            "scientific_name": "Pilea peperomioides",
                            "common_name": "Chinese money plant",
                            "confidence_label": "medium",
                            "confidence_score": 0.72,
                            "visible_traits": ["round leaves"],
                        }
                    ],
                }
            )

    models = FakeModels()
    provider = GeminiVisionProvider(
        api_key="test-key",
        model="gemini-2.5-flash",
        client=types.SimpleNamespace(aio=types.SimpleNamespace(models=models)),
    )

    result = await provider.analyze_image(
        b"png-bytes", prompt="Endpoint prompt.", mime_type="image/png", temperature=0
    )

    assert models.kwargs is not None
    assert models.kwargs["model"] == "gemini-2.5-flash"
    assert models.kwargs["contents"][0].startswith("Endpoint prompt.")
    assert models.kwargs["contents"][1] == {"data": b"png-bytes", "mime_type": "image/png"}
    assert models.kwargs["config"].kwargs["response_mime_type"] == "application/json"
    assert result.provider == "gemini-vision"
    assert result.description == "round green leaves"
    assert result.candidates[0].scientific_name == "Pilea peperomioides"
    assert result.candidates[0].provider == "gemini-vision"

def test_gemini_vision_schema_is_sdk_compatible() -> None:
    genai_types = pytest.importorskip("google.genai.types")

    schema = genai_types.Schema.model_validate(_VISION_SCHEMA)
    candidate_schema = schema.properties["candidates"].items.properties

    assert candidate_schema["common_name"].nullable is True
    assert candidate_schema["confidence_score"].nullable is True

def test_gemini_vision_schema_uses_nullable_fields() -> None:
    candidate_schema = _VISION_SCHEMA["properties"]["candidates"]["items"]["properties"]

    assert candidate_schema["common_name"] == {"type": "string", "nullable": True}
    assert candidate_schema["confidence_score"] == {"type": "number", "nullable": True}

def test_gemini_judge_schema_aspect_arrays_are_enum_constrained() -> None:
    from app.assistant.care_contracts import RequiredAspect

    aspect_values = [item.value for item in RequiredAspect]
    covered_items = _JUDGE_SCHEMA["properties"]["covered_aspects"]["items"]
    missing_items = _JUDGE_SCHEMA["properties"]["missing_aspects"]["items"]
    source_items = _JUDGE_SCHEMA["properties"]["source_support"]["items"]["properties"]["covered_aspects"]["items"]

    assert covered_items["enum"] == aspect_values
    assert missing_items["enum"] == aspect_values
    assert source_items["enum"] == aspect_values

@pytest.mark.asyncio
async def test_gemini_judge_maps_response(fake_gemini_module: None) -> None:
    class FakeModels:
        async def generate_content(self, **kwargs: object) -> object:
            return types.SimpleNamespace(
                text=(
                    '{"status":"partial","covered_aspects":["light_exposure"],'
                    '"missing_aspects":["watering_frequency_or_trigger"],'
                    '"source_support":[{"claim":"light is supported",'
                    '"source_urls":["https://example.org/light"],'
                    '"covered_aspects":["light_exposure"],'
                    '"evidence_quote":"bright indirect light","confidence":0.75}],'
                    '"contradictions":[{"claim_a":"Water weekly",'
                    '"claim_b":"Water monthly",'
                    '"source_a_urls":["https://example.org/a"],'
                    '"source_b_urls":["https://example.org/b"]}],'
                    '"confidence":0.75,"score":0.75,'
                    '"passed":false,"reasons":["weak grounding"]}'
                )
            )

    provider = GeminiJudgeProvider(
        api_key="test-key",
        model="gemini-2.5-flash",
        client=types.SimpleNamespace(aio=types.SimpleNamespace(models=FakeModels())),
    )

    result = await provider.judge_response({"answer": "x"}, {"passing_score": 0.8})

    assert result.provider == "gemini-judge"
    assert result.model == "gemini-2.5-flash"
    assert result.score == 0.75
    assert result.passed is False
    assert result.reasons == ["weak grounding"]
    assert result.status == "partial"
    assert result.covered_aspects == ["light_exposure"]
    assert result.missing_aspects == ["watering_frequency_or_trigger"]
    assert result.source_support[0]["source_urls"] == ["https://example.org/light"]
    assert result.contradictions == [
        {
            "claim_a": "Water weekly",
            "claim_b": "Water monthly",
            "source_a_urls": ["https://example.org/a"],
            "source_b_urls": ["https://example.org/b"],
        }
    ]
    assert result.confidence == 0.75

@pytest.mark.asyncio
async def test_gemini_search_maps_grounded_citations(fake_gemini_module: None) -> None:
    class FakeModels:
        def __init__(self) -> None:
            self.kwargs: dict[str, object] | None = None

        async def generate_content(self, **kwargs: object) -> object:
            self.kwargs = kwargs
            return types.SimpleNamespace(
                text="Use the RHS guide for watering.",
                candidates=[
                    types.SimpleNamespace(
                        grounding_metadata=types.SimpleNamespace(
                            grounding_chunks=[
                                types.SimpleNamespace(
                                    web=types.SimpleNamespace(
                                        uri="https://www.rhs.org.uk/plants/cotyledon",
                                        title="RHS Cotyledon guide",
                                    )
                                )
                            ],
                            grounding_supports=[
                                types.SimpleNamespace(
                                    segment=types.SimpleNamespace(
                                        text="Use the RHS guide for watering.",
                                    ),
                                    grounding_chunk_indices=[0],
                                )
                            ],
                        )
                    )
                ],
            )

    models = FakeModels()
    provider = GeminiSearchProvider(
        api_key="test-key",
        model="gemini-2.5-flash",
        client=types.SimpleNamespace(aio=types.SimpleNamespace(models=models)),
    )

    results = await provider.search("Cotyledon watering", allowed_domains=["www.rhs.org.uk"])

    assert models.kwargs is not None
    assert models.kwargs["model"] == "gemini-2.5-flash"
    assert "www.rhs.org.uk" in models.kwargs["contents"]
    assert models.kwargs["config"].kwargs["tools"][0].kwargs
    assert results == [
        SearchResult(
            title="RHS Cotyledon guide",
            url="https://www.rhs.org.uk/plants/cotyledon",
            snippet="Use the RHS guide for watering.",
            source_domain="www.rhs.org.uk",
            metadata={"snippet_source": "grounding_support"},
        )
    ]

