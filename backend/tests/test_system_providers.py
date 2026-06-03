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
from app.providers.plant_data import PerenualPlantDataProvider, TreflePlantDataProvider


@pytest.fixture(autouse=True)
def reset_provider_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MODEL_PROVIDER", "mock")
    monkeypatch.setenv("VISION_PROVIDER", "mock")
    monkeypatch.setenv("JUDGE_PROVIDER", "mock")
    monkeypatch.setenv("SEARCH_PROVIDER", "mock")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "mock")
    monkeypatch.setenv("TREFLE_PROVIDER", "mock")
    monkeypatch.setenv("PERENUAL_PROVIDER", "mock")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("TREFLE_API_KEY", "")
    monkeypatch.setenv("PERENUAL_API_KEY", "")
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
    assert payload["dependencies"]["trefle_provider"] == "MockTreflePlantDataProvider"
    assert payload["dependencies"]["perenual_provider"] == "MockPerenualPlantDataProvider"


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
    trefle = await providers.trefle.lookup("Cotyledon tomentosa")
    perenual = await providers.perenual.lookup("Cotyledon tomentosa")

    assert text.provider == "mock-model"
    assert image.candidates[0].scientific_name == "Cotyledon tomentosa"
    assert judge.provider == "mock-model"
    assert search[0].source_domain == "example.org"
    assert embeddings.provider == "mock-embedding"
    assert len(embeddings.embeddings[0]) > 0
    assert trefle.provider == "mock-trefle"
    assert perenual.provider == "mock-perenual"


@pytest.mark.asyncio
async def test_real_trefle_provider_fetches_detail_after_exact_search_match(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    async def fake_fetch_json(url: str) -> dict[str, object]:
        calls.append(url)
        if "/plants/search" in url:
            return {
                "data": [
                    {
                        "scientific_name": "Cotyledon tomentosa",
                        "slug": "cotyledon-tomentosa",
                        "links": {"self": "/api/v1/species/cotyledon-tomentosa"},
                    }
                ]
            }
        return {
            "data": {
                "scientific_name": "Cotyledon tomentosa",
                "common_name": "Bear paw succulent",
                "family": "Crassulaceae",
                "genus": "Cotyledon",
                "rank": "species",
                "growth": {"description": "Compact succulent growth."},
                "links": {"self": "/api/v1/species/cotyledon-tomentosa"},
            }
        }

    monkeypatch.setattr("app.providers.plant_data._fetch_json", fake_fetch_json)

    result = await TreflePlantDataProvider(api_key="test-token").lookup("Cotyledon tomentosa")

    assert result is not None
    assert calls[0].startswith("https://trefle.io/api/v1/plants/search?")
    assert "/api/v1/species/cotyledon-tomentosa?token=test-token" in calls[1]
    assert result.source_url == "https://trefle.io/api/v1/species/cotyledon-tomentosa"
    assert result.fields["description"] == "Compact succulent growth."


@pytest.mark.asyncio
async def test_real_trefle_provider_uses_slug_match_before_normalized_name_match(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_fetch_json(url: str) -> dict[str, object]:
        if "/plants/search" in url:
            return {
                "data": [
                    {
                        "scientific_name": "Other species",
                        "slug": "other-species",
                        "synonyms": ["Cotyledon tomentosa"],
                    },
                    {
                        "scientific_name": "Cotyledon tomentosa Harv.",
                        "slug": "cotyledon-tomentosa",
                    },
                ]
            }
        assert "/api/v1/species/cotyledon-tomentosa" in url
        return {
            "data": {
                "scientific_name": "Cotyledon tomentosa Harv.",
                "family": "Crassulaceae",
                "links": {"self": "/api/v1/species/cotyledon-tomentosa"},
            }
        }

    monkeypatch.setattr("app.providers.plant_data._fetch_json", fake_fetch_json)

    result = await TreflePlantDataProvider(api_key="test-token").lookup("Cotyledon tomentosa")

    assert result is not None
    assert result.scientific_name == "Cotyledon tomentosa Harv."


@pytest.mark.asyncio
async def test_real_trefle_provider_uses_normalized_synonym_match(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_fetch_json(url: str) -> dict[str, object]:
        if "/plants/search" in url:
            return {
                "data": [
                    {
                        "scientific_name": "Cotyledon ladismithiensis",
                        "slug": "cotyledon-ladismithiensis",
                        "synonyms": ["Cotyledon tomentosa"],
                    }
                ]
            }
        return {
            "data": {
                "scientific_name": "Cotyledon ladismithiensis",
                "links": {"self": "/api/v1/species/cotyledon-ladismithiensis"},
            }
        }

    monkeypatch.setattr("app.providers.plant_data._fetch_json", fake_fetch_json)

    result = await TreflePlantDataProvider(api_key="test-token").lookup("Cotyledon tomentosa")

    assert result is not None
    assert result.scientific_name == "Cotyledon ladismithiensis"


@pytest.mark.asyncio
async def test_real_trefle_provider_returns_none_when_search_has_no_match(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    async def fake_fetch_json(url: str) -> dict[str, object]:
        calls.append(url)
        return {"data": [{"scientific_name": "Cocos nucifera", "slug": "cocos-nucifera"}]}

    monkeypatch.setattr("app.providers.plant_data._fetch_json", fake_fetch_json)

    result = await TreflePlantDataProvider(api_key="test-token").lookup("Cotyledon tomentosa")

    assert result is None
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_real_perenual_provider_searches_binomial_but_prefers_full_exact_match(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    async def fake_fetch_json(url: str) -> dict[str, object]:
        calls.append(url)
        if "/species-list" in url:
            return {
                "data": [
                    {
                        "id": 1,
                        "common_name": "Bear paw",
                        "scientific_name": ["Cotyledon tomentosa"],
                        "genus": "Cotyledon",
                    },
                    {
                        "id": 2,
                        "common_name": "Bear paw subspecies",
                        "scientific_name": ["Cotyledon tomentosa ladismithiensis"],
                        "genus": "Cotyledon",
                    },
                ]
            }
        assert "/species/details/2?" in url
        return {
            "id": 2,
            "common_name": "Bear paw subspecies",
            "scientific_name": ["Cotyledon tomentosa ladismithiensis"],
            "family": "Crassulaceae",
            "genus": "Cotyledon",
            "watering": "Minimum",
            "sunlight": ["full sun"],
            "soil": ["Well-drained"],
        }

    monkeypatch.setattr("app.providers.plant_data._fetch_json", fake_fetch_json)

    result = await PerenualPlantDataProvider(api_key="test-key").lookup(
        "Cotyledon tomentosa ladismithiensis"
    )

    assert result is not None
    assert calls[0].startswith("https://perenual.com/api/v2/species-list?")
    assert "q=Cotyledon+tomentosa" in calls[0]
    assert result.scientific_name == "Cotyledon tomentosa ladismithiensis"
    assert result.family == "Crassulaceae"
    assert result.fields["watering"] == "Minimum"


@pytest.mark.asyncio
async def test_real_perenual_provider_handles_scientific_name_list_exact_match(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_fetch_json(url: str) -> dict[str, object]:
        if "/species-list" in url:
            return {
                "data": [
                    {
                        "id": 1,
                        "scientific_name": ["Abies alba"],
                        "other_name": ["Common Silver Fir"],
                    },
                    {
                        "id": 2,
                        "scientific_name": ["Abies alba 'Pyramidalis'"],
                    },
                ]
            }
        assert "/species/details/1?" in url
        return {
            "id": 1,
            "common_name": "European Silver Fir",
            "scientific_name": ["Abies alba"],
            "watering": "Frequent",
        }

    monkeypatch.setattr("app.providers.plant_data._fetch_json", fake_fetch_json)

    result = await PerenualPlantDataProvider(api_key="test-key").lookup("Abies alba")

    assert result is not None
    assert result.scientific_name == "Abies alba"
    assert result.common_name == "European Silver Fir"


@pytest.mark.asyncio
async def test_real_perenual_provider_returns_none_when_search_has_no_match(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    async def fake_fetch_json(url: str) -> dict[str, object]:
        calls.append(url)
        return {"data": [{"id": 1, "scientific_name": ["Cocos nucifera"]}]}

    monkeypatch.setattr("app.providers.plant_data._fetch_json", fake_fetch_json)

    result = await PerenualPlantDataProvider(api_key="test-key").lookup("Cotyledon tomentosa")

    assert result is None
    assert len(calls) == 1


def test_real_trefle_provider_requires_only_trefle_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TREFLE_PROVIDER", "real")
    get_settings.cache_clear()

    with pytest.raises(
        ValueError, match="TREFLE_API_KEY is required when trefle provider is real"
    ):
        get_provider_registry()

    monkeypatch.setenv("TREFLE_API_KEY", "test-trefle")
    get_settings.cache_clear()

    providers = get_provider_registry()
    assert isinstance(providers.trefle, TreflePlantDataProvider)
    assert providers.perenual.__class__.__name__ == "MockPerenualPlantDataProvider"


def test_real_perenual_provider_requires_only_perenual_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PERENUAL_PROVIDER", "real")
    get_settings.cache_clear()

    with pytest.raises(
        ValueError, match="PERENUAL_API_KEY is required when perenual provider is real"
    ):
        get_provider_registry()

    monkeypatch.setenv("PERENUAL_API_KEY", "test-perenual")
    get_settings.cache_clear()

    providers = get_provider_registry()
    assert isinstance(providers.perenual, PerenualPlantDataProvider)
    assert providers.trefle.__class__.__name__ == "MockTreflePlantDataProvider"


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
