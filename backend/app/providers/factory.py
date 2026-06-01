from dataclasses import dataclass

from app.core.settings import get_settings
from app.providers.interfaces import (
    EmbeddingProvider,
    ImageAnalysisProvider,
    JudgeEvaluationProvider,
    ModelProvider,
    SearchProvider,
)
from app.providers.mocks import (
    MockEmbeddingProvider,
    MockModelProvider,
    MockSearchProvider,
    MockVisionPlantIdentificationProvider,
)
from app.providers.openai import OpenAIJudgeProvider, OpenAIModelProvider, OpenAIVisionProvider


@dataclass(frozen=True)
class ProviderRegistry:
    model: ModelProvider
    vision: ImageAnalysisProvider
    judge: JudgeEvaluationProvider
    search: SearchProvider
    embeddings: EmbeddingProvider


def get_provider_registry() -> ProviderRegistry:
    settings = get_settings()

    return ProviderRegistry(
        model=_build_model_provider(settings.model_provider, settings),
        vision=_build_vision_provider(settings.vision_provider, settings),
        judge=_build_judge_provider(settings.judge_provider, settings),
        search=_build_search_provider(settings.search_provider),
        embeddings=_build_embedding_provider(settings.embedding_provider),
    )


def _normalize_provider(value: str) -> str:
    return value.strip().lower()


def _require_openai_api_key(value: str | None, *, role: str) -> str:
    if not value:
        raise ValueError(f"OPENAI_API_KEY is required when {role} provider is openai")
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


def _build_search_provider(provider: str) -> SearchProvider:
    match _normalize_provider(provider):
        case "mock":
            return MockSearchProvider()
    raise ValueError(f"Unsupported search provider: {provider}")


def _build_embedding_provider(provider: str) -> EmbeddingProvider:
    match _normalize_provider(provider):
        case "mock":
            return MockEmbeddingProvider()
    raise ValueError(f"Unsupported embedding provider: {provider}")
