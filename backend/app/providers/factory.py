from dataclasses import dataclass

from app.core.settings import get_settings
from app.providers.interfaces import (
    EmbeddingProvider,
    ImageAnalysisProvider,
    JudgeEvaluationProvider,
    ModelProvider,
    PlantDataProvider,
    SearchProvider,
)
from app.providers.mocks import (
    MockEmbeddingProvider,
    MockModelProvider,
    MockPerenualPlantDataProvider,
    MockSearchProvider,
    MockTreflePlantDataProvider,
    MockVisionPlantIdentificationProvider,
)
from app.providers.openai import (
    OpenAIEmbeddingProvider,
    OpenAIJudgeProvider,
    OpenAIModelProvider,
    OpenAISearchProvider,
    OpenAIVisionProvider,
)
from app.providers.plant_data import PerenualPlantDataProvider, TreflePlantDataProvider


@dataclass(frozen=True)
class ProviderRegistry:
    model: ModelProvider
    vision: ImageAnalysisProvider
    judge: JudgeEvaluationProvider
    search: SearchProvider
    embeddings: EmbeddingProvider
    trefle: PlantDataProvider
    perenual: PlantDataProvider


def get_provider_registry() -> ProviderRegistry:
    settings = get_settings()

    return ProviderRegistry(
        model=_build_model_provider(settings.model_provider, settings),
        vision=_build_vision_provider(settings.vision_provider, settings),
        judge=_build_judge_provider(settings.judge_provider, settings),
        search=_build_search_provider(settings.search_provider, settings),
        embeddings=_build_embedding_provider(settings.embedding_provider, settings),
        trefle=_build_trefle_provider(settings.trefle_provider, settings),
        perenual=_build_perenual_provider(settings.perenual_provider, settings),
    )


def _normalize_provider(value: str) -> str:
    return value.strip().lower()


def _require_openai_api_key(value: str | None, *, role: str) -> str:
    if not value:
        raise ValueError(f"OPENAI_API_KEY is required when {role} provider is openai")
    return value


def _require_api_key(value: str | None, *, env_name: str, role: str) -> str:
    if not value:
        raise ValueError(f"{env_name} is required when {role} provider is real")
    return value


def _build_model_provider(provider: str, settings: object) -> ModelProvider:
    match _normalize_provider(provider):
        case "mock":
            return MockModelProvider()
        case "openai":
            return OpenAIModelProvider(
                api_key=_require_openai_api_key(settings.openai_api_key, role="model"),
                model=settings.openai_text_model,
            )
    raise ValueError(f"Unsupported model provider: {provider}")


def _build_vision_provider(provider: str, settings: object) -> ImageAnalysisProvider:
    match _normalize_provider(provider):
        case "mock":
            return MockVisionPlantIdentificationProvider()
        case "openai":
            return OpenAIVisionProvider(
                api_key=_require_openai_api_key(settings.openai_api_key, role="vision"),
                model=settings.openai_vision_model,
            )
    raise ValueError(f"Unsupported vision provider: {provider}")


def _build_judge_provider(provider: str, settings: object) -> JudgeEvaluationProvider:
    match _normalize_provider(provider):
        case "mock":
            return MockModelProvider()
        case "openai":
            return OpenAIJudgeProvider(
                api_key=_require_openai_api_key(settings.openai_api_key, role="judge"),
                model=settings.openai_judge_model,
            )
    raise ValueError(f"Unsupported judge provider: {provider}")


def _build_search_provider(provider: str, settings: object) -> SearchProvider:
    match _normalize_provider(provider):
        case "mock":
            return MockSearchProvider()
        case "openai":
            return OpenAISearchProvider(
                api_key=_require_openai_api_key(settings.openai_api_key, role="search"),
                model=settings.openai_search_model,
            )
    raise ValueError(f"Unsupported search provider: {provider}")


def _build_embedding_provider(provider: str, settings: object) -> EmbeddingProvider:
    match _normalize_provider(provider):
        case "mock":
            return MockEmbeddingProvider()
        case "openai":
            return OpenAIEmbeddingProvider(
                api_key=_require_openai_api_key(settings.openai_api_key, role="embedding"),
                model=settings.openai_embedding_model,
                embedding_dimension=settings.embedding_dimension,
            )
    raise ValueError(f"Unsupported embedding provider: {provider}")


def _build_trefle_provider(provider: str, settings: object) -> PlantDataProvider:
    match _normalize_provider(provider):
        case "mock":
            return MockTreflePlantDataProvider()
        case "real" | "trefle":
            return TreflePlantDataProvider(
                api_key=_require_api_key(
                    settings.trefle_api_key, env_name="TREFLE_API_KEY", role="trefle"
                )
            )
    raise ValueError(f"Unsupported trefle provider: {provider}")


def _build_perenual_provider(provider: str, settings: object) -> PlantDataProvider:
    match _normalize_provider(provider):
        case "mock":
            return MockPerenualPlantDataProvider()
        case "real" | "perenual":
            return PerenualPlantDataProvider(
                api_key=_require_api_key(
                    settings.perenual_api_key, env_name="PERENUAL_API_KEY", role="perenual"
                )
            )
    raise ValueError(f"Unsupported perenual provider: {provider}")
