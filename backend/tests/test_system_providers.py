import sys
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
    OpenAIJudgeProvider,
    OpenAIModelProvider,
    OpenAIProviderError,
    OpenAISearchProvider,
    OpenAIVisionProvider,
)
from app.providers.plant_data import PerenualPlantDataProvider, TreflePlantDataProvider
from app.providers.types import SearchResult


@pytest.fixture(autouse=True)
def reset_provider_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    for chain_var in (
        "MODEL_PROVIDERS",
        "JUDGE_PROVIDERS",
        "SEARCH_PROVIDERS",
        "VISION_PROVIDERS",
    ):
        monkeypatch.setenv(chain_var, "[]")
    monkeypatch.setenv("MODEL_PROVIDER", "mock")
    monkeypatch.setenv("VISION_PROVIDER", "mock")
    monkeypatch.setenv("JUDGE_PROVIDER", "mock")
    monkeypatch.setenv("SEARCH_PROVIDER", "mock")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "mock")
    monkeypatch.setenv("TREFLE_PROVIDER", "mock")
    monkeypatch.setenv("PERENUAL_PROVIDER", "mock")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("GEMINI_API_KEY", "")
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


@pytest.fixture
def fake_gemini_module(monkeypatch: pytest.MonkeyPatch) -> None:
    google_module = types.ModuleType("google")
    genai_module = types.ModuleType("google.genai")
    genai_types_module = types.ModuleType("google.genai.types")

    class FakeGenerateContentConfig:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs

    class FakePart:
        @staticmethod
        def from_bytes(*, data: bytes, mime_type: str) -> dict[str, object]:
            return {"data": data, "mime_type": mime_type}

    class FakeGoogleSearch:
        pass

    class FakeTool:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs

    class FakeModels:
        async def generate_content(self, **kwargs: object) -> object:
            return types.SimpleNamespace(text='{"score": 1, "passed": true, "reasons": []}')

    class FakeClient:
        def __init__(self, *, api_key: str) -> None:
            self.api_key = api_key
            self.aio = types.SimpleNamespace(models=FakeModels())

    genai_types_module.GenerateContentConfig = FakeGenerateContentConfig
    genai_types_module.Part = FakePart
    genai_types_module.GoogleSearch = FakeGoogleSearch
    genai_types_module.Tool = FakeTool
    genai_module.Client = FakeClient
    genai_module.types = genai_types_module
    google_module.genai = genai_module
    monkeypatch.setitem(sys.modules, "google", google_module)
    monkeypatch.setitem(sys.modules, "google.genai", genai_module)
    monkeypatch.setitem(sys.modules, "google.genai.types", genai_types_module)


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
async def test_real_perenual_provider_searches_and_matches_binomial_name(
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
                        "scientific_name": ["Cotyledon tomentosa"],
                        "genus": "Cotyledon",
                    },
                ]
            }
        assert "/species/details/1?" in url
        return {
            "id": 1,
            "common_name": "Bear paw",
            "scientific_name": ["Cotyledon tomentosa"],
            "family": "Crassulaceae",
            "genus": "Cotyledon",
            "watering": "Minimum",
            "sunlight": ["full sun"],
            "soil": ["Well-drained"],
        }

    monkeypatch.setattr("app.providers.plant_data._fetch_json", fake_fetch_json)

    result = await PerenualPlantDataProvider(api_key="test-key").lookup(
        "Cotyledon tomentosa"
    )

    assert result is not None
    assert calls[0].startswith("https://perenual.com/api/v2/species-list?")
    assert "q=Cotyledon+tomentosa" in calls[0]
    assert result.scientific_name == "Cotyledon tomentosa"
    assert result.family == "Crassulaceae"
    assert result.fields["watering"]["description"] == "Minimum"


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


def test_gemini_model_selection_does_not_change_search_or_embeddings(
    monkeypatch: pytest.MonkeyPatch,
    fake_gemini_module: None,
) -> None:
    monkeypatch.setenv("MODEL_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    get_settings.cache_clear()

    providers = get_provider_registry()

    assert isinstance(providers.model, GeminiModelProvider)
    assert providers.search.__class__.__name__ == "MockSearchProvider"
    assert providers.embeddings.__class__.__name__ == "MockEmbeddingProvider"


def test_gemini_vision_selection_does_not_change_model_provider(
    monkeypatch: pytest.MonkeyPatch,
    fake_gemini_module: None,
) -> None:
    monkeypatch.setenv("VISION_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    get_settings.cache_clear()

    providers = get_provider_registry()

    assert isinstance(providers.vision, GeminiVisionProvider)
    assert providers.model.__class__.__name__ == "MockModelProvider"


def test_gemini_judge_selection_does_not_change_runtime_generation_provider(
    monkeypatch: pytest.MonkeyPatch,
    fake_gemini_module: None,
) -> None:
    monkeypatch.setenv("JUDGE_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    get_settings.cache_clear()

    providers = get_provider_registry()

    assert isinstance(providers.judge, GeminiJudgeProvider)
    assert providers.model.__class__.__name__ == "MockModelProvider"


def test_gemini_roles_can_be_selected_independently(
    monkeypatch: pytest.MonkeyPatch,
    fake_gemini_module: None,
) -> None:
    monkeypatch.setenv("MODEL_PROVIDER", "gemini")
    monkeypatch.setenv("VISION_PROVIDER", "gemini")
    monkeypatch.setenv("JUDGE_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_TEXT_MODEL", "gemini-text-test")
    monkeypatch.setenv("GEMINI_VISION_MODEL", "gemini-vision-test")
    monkeypatch.setenv("GEMINI_JUDGE_MODEL", "gemini-judge-test")
    get_settings.cache_clear()

    providers = get_provider_registry()

    assert isinstance(providers.model, GeminiModelProvider)
    assert isinstance(providers.vision, GeminiVisionProvider)
    assert isinstance(providers.judge, GeminiJudgeProvider)
    assert providers.model.model == "gemini-text-test"
    assert providers.vision.model == "gemini-vision-test"
    assert providers.judge.model == "gemini-judge-test"
    assert providers.search.__class__.__name__ == "MockSearchProvider"
    assert providers.embeddings.__class__.__name__ == "MockEmbeddingProvider"


def test_gemini_search_selection_does_not_change_other_providers(
    monkeypatch: pytest.MonkeyPatch,
    fake_gemini_module: None,
) -> None:
    monkeypatch.setenv("SEARCH_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_SEARCH_MODEL", "gemini-search-test")
    get_settings.cache_clear()

    providers = get_provider_registry()

    assert isinstance(providers.search, GeminiSearchProvider)
    assert providers.search.model == "gemini-search-test"
    assert providers.model.__class__.__name__ == "MockModelProvider"
    assert providers.vision.__class__.__name__ == "MockVisionPlantIdentificationProvider"
    assert providers.judge.__class__.__name__ == "MockModelProvider"
    assert providers.embeddings.__class__.__name__ == "MockEmbeddingProvider"


def test_all_gemini_roles_except_embeddings_can_be_selected(
    monkeypatch: pytest.MonkeyPatch,
    fake_gemini_module: None,
    fake_openai_module: None,
) -> None:
    monkeypatch.setenv("MODEL_PROVIDER", "gemini")
    monkeypatch.setenv("VISION_PROVIDER", "gemini")
    monkeypatch.setenv("JUDGE_PROVIDER", "gemini")
    monkeypatch.setenv("SEARCH_PROVIDER", "gemini")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "openai")
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    get_settings.cache_clear()

    providers = get_provider_registry()

    assert isinstance(providers.model, GeminiModelProvider)
    assert isinstance(providers.vision, GeminiVisionProvider)
    assert isinstance(providers.judge, GeminiJudgeProvider)
    assert isinstance(providers.search, GeminiSearchProvider)
    assert isinstance(providers.embeddings, OpenAIEmbeddingProvider)


def test_missing_gemini_credentials_only_fail_selected_gemini_roles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MODEL_PROVIDER", "gemini")
    get_settings.cache_clear()

    with pytest.raises(
        ValueError, match="GEMINI_API_KEY is required when model provider is gemini"
    ):
        get_provider_registry()

    monkeypatch.setenv("MODEL_PROVIDER", "mock")
    get_settings.cache_clear()

    providers = get_provider_registry()
    assert providers.model.__class__.__name__ == "MockModelProvider"


def test_missing_gemini_credentials_fail_for_selected_vision_role(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VISION_PROVIDER", "gemini")
    get_settings.cache_clear()

    with pytest.raises(
        ValueError, match="GEMINI_API_KEY is required when vision provider is gemini"
    ):
        get_provider_registry()


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

    monkeypatch.setattr("app.providers.gemini.log_provider_call", fake_log_provider_call)
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
        monkey.setattr("app.providers.openai.logger", _StubLogger())
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
        monkey.setattr("app.providers.openai.logger", _StubLogger())
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
