import sys
import types

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.settings import get_settings
from app.main import app
from app.providers.factory import get_provider_registry
from app.providers.openai import (
    OpenAIEmbeddingProvider,
    OpenAIJudgeProvider,
    OpenAIModelProvider,
    OpenAIProviderError,
    OpenAISearchProvider,
    OpenAIVisionProvider,
)


@pytest.fixture(autouse=True)
def reset_provider_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MODEL_PROVIDER", "mock")
    monkeypatch.setenv("VISION_PROVIDER", "mock")
    monkeypatch.setenv("JUDGE_PROVIDER", "mock")
    monkeypatch.setenv("SEARCH_PROVIDER", "mock")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "mock")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def fake_openai_module(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeResponses:
        async def create(self, **kwargs: object) -> object:
            return types.SimpleNamespace(output_text='{"score": 1, "passed": true, "reasons": []}')

    class FakeEmbeddings:
        async def create(self, **kwargs: object) -> object:
            return types.SimpleNamespace(
                data=[types.SimpleNamespace(index=0, embedding=[0.1, 0.2, 0.3])],
                usage=types.SimpleNamespace(prompt_tokens=3, total_tokens=3),
            )

    class FakeAsyncOpenAI:
        def __init__(self, *, api_key: str) -> None:
            self.api_key = api_key
            self.responses = FakeResponses()
            self.embeddings = FakeEmbeddings()

    monkeypatch.setitem(sys.modules, "openai", types.SimpleNamespace(AsyncOpenAI=FakeAsyncOpenAI))


@pytest.mark.asyncio
async def test_health_reports_mock_provider_dependencies() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["dependencies"]["model_provider"] == "MockModelProvider"
    assert payload["dependencies"]["vision_provider"] == "MockVisionPlantIdentificationProvider"
    assert payload["dependencies"]["judge_provider"] == "MockModelProvider"
    assert payload["dependencies"]["embedding_provider"] == "MockEmbeddingProvider"
    assert payload["dependencies"]["search_provider"] == "MockSearchProvider"


@pytest.mark.asyncio
async def test_metrics_endpoint_exposes_prometheus_text() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.get("/health")
        response = await client.get("/metrics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "fotosintesis_requests_total" in response.text


@pytest.mark.asyncio
async def test_mock_provider_registry_returns_deterministic_local_providers() -> None:
    providers = get_provider_registry()

    text = await providers.model.generate_text("care prompt")
    image = await providers.vision.analyze_image(b"fake-image")
    judge = await providers.judge.judge_response({}, {})
    search = await providers.search.search("Cotyledon tomentosa care")
    embeddings = await providers.embeddings.create_embeddings(["bright light"])

    assert text.provider == "mock-model"
    assert image.candidates[0].scientific_name == "Cotyledon tomentosa"
    assert judge.provider == "mock-model"
    assert search[0].source_domain == "example.org"
    assert embeddings.provider == "mock-embedding"
    assert len(embeddings.embeddings[0]) > 0


def test_openai_model_selection_does_not_change_search_or_embeddings(
    monkeypatch: pytest.MonkeyPatch,
    fake_openai_module: None,
) -> None:
    monkeypatch.setenv("MODEL_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    get_settings.cache_clear()

    providers = get_provider_registry()

    assert isinstance(providers.model, OpenAIModelProvider)
    assert providers.search.__class__.__name__ == "MockSearchProvider"
    assert providers.embeddings.__class__.__name__ == "MockEmbeddingProvider"


def test_openai_vision_selection_does_not_change_model_provider(
    monkeypatch: pytest.MonkeyPatch,
    fake_openai_module: None,
) -> None:
    monkeypatch.setenv("VISION_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    get_settings.cache_clear()

    providers = get_provider_registry()

    assert isinstance(providers.vision, OpenAIVisionProvider)
    assert providers.model.__class__.__name__ == "MockModelProvider"


@pytest.mark.asyncio
async def test_openai_vision_uses_mime_type_without_forwarding_kwarg(
    fake_openai_module: None,
) -> None:
    class FakeResponses:
        def __init__(self) -> None:
            self.kwargs: dict[str, object] | None = None

        async def create(self, **kwargs: object) -> object:
            self.kwargs = kwargs
            return types.SimpleNamespace(
                output_text=(
                    '{"description": "green leaves", "candidates": ['
                    '{"scientific_name": "Pilea peperomioides", "common_name": "Chinese money plant", '
                    '"confidence_label": "medium", "confidence_score": 0.72, '
                    '"visible_traits": ["round leaves"]}]}'
                )
            )

    responses = FakeResponses()
    provider = OpenAIVisionProvider(api_key="test-key", model="gpt-4.1-mini")
    provider._client = types.SimpleNamespace(responses=responses)

    result = await provider.analyze_image(
        b"png-bytes", prompt="Endpoint prompt.", mime_type="image/png", temperature=0
    )

    assert responses.kwargs is not None
    assert "mime_type" not in responses.kwargs
    content = responses.kwargs["input"][0]["content"]  # type: ignore[index]
    assert content[0]["text"].startswith("Endpoint prompt.")
    assert "Return only valid JSON" in content[0]["text"]
    assert content[1]["image_url"].startswith("data:image/png;base64,")
    assert result.description == "green leaves"
    assert result.candidates[0].scientific_name == "Pilea peperomioides"
    assert result.candidates[0].provider == "openai-vision"


def test_openai_judge_selection_does_not_change_runtime_generation_provider(
    monkeypatch: pytest.MonkeyPatch,
    fake_openai_module: None,
) -> None:
    monkeypatch.setenv("JUDGE_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    get_settings.cache_clear()

    providers = get_provider_registry()

    assert isinstance(providers.judge, OpenAIJudgeProvider)
    assert providers.model.__class__.__name__ == "MockModelProvider"


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

    monkeypatch.setattr("app.providers.openai.log_provider_call", fake_log_provider_call)
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
