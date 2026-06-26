from __future__ import annotations

from dataclasses import dataclass

from app.core.settings import Settings, get_settings
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
from app.providers.gemini import (
    GeminiJudgeProvider,
    GeminiModelProvider,
    GeminiSearchProvider,
    GeminiVisionProvider,
)
from app.providers.openai import (
    OpenAIEmbeddingProvider,
    OpenAIJudgeProvider,
    OpenAIModelProvider,
    OpenAISearchProvider,
    OpenAIVisionProvider,
)
from app.providers.plant_data import PerenualPlantDataProvider, TreflePlantDataProvider
from app.providers.wrappers import (
    ImageAnalysisProviderFallbackWrapper,
    JudgeEvaluationProviderFallbackWrapper,
    ModelProviderFallbackWrapper,
    SearchProviderFallbackWrapper,
)


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

    model_providers = _resolve_provider_chain(
        settings.model_providers, settings.model_provider, "model"
    )
    judge_providers = _resolve_provider_chain(
        settings.judge_providers, settings.judge_provider, "judge"
    )
    search_providers = _resolve_provider_chain(
        settings.search_providers, settings.search_provider, "search"
    )
    vision_providers = _resolve_provider_chain(
        settings.vision_providers, settings.vision_provider, "vision"
    )

    return ProviderRegistry(
        model=_build_model_chain(model_providers, settings),
        vision=_build_vision_chain(vision_providers, settings),
        judge=_build_judge_chain(judge_providers, settings),
        search=_build_search_chain(search_providers, settings),
        embeddings=_build_embedding_provider(settings.embedding_provider, settings),
        trefle=_build_trefle_provider(settings.trefle_provider, settings),
        perenual=_build_perenual_provider(settings.perenual_provider, settings),
    )


def _resolve_provider_chain(
    chain: list[str] | None, single: str, role: str
) -> list[str]:
    if chain:
        return chain
    return [single]


def _normalize_provider(value: str) -> str:
    return value.strip().lower()


def _require_openai_api_key(value: str | None, *, role: str) -> str:
    if not value:
        raise ValueError(f"OPENAI_API_KEY is required when {role} provider is openai")
    return value


def _require_gemini_api_key(value: str | None, *, role: str) -> str:
    if not value:
        raise ValueError(f"GEMINI_API_KEY is required when {role} provider is gemini")
    return value


def _require_api_key(value: str | None, *, env_name: str, role: str) -> str:
    if not value:
        raise ValueError(f"{env_name} is required when {role} provider is real")
    return value


def _is_local_or_dev(settings: Settings) -> bool:
    return settings.environment in ("local", "dev", "development", "")


def _build_single_model_provider(provider: str, settings: Settings) -> ModelProvider:
    match _normalize_provider(provider):
        case "mock":
            return MockModelProvider()
        case "openai":
            return OpenAIModelProvider(
                api_key=_require_openai_api_key(settings.openai_api_key, role="model"),
                model=settings.openai_text_model,
                classifier_model=settings.openai_classifier_model,
            )
        case "gemini":
            return GeminiModelProvider(
                api_key=_require_gemini_api_key(settings.gemini_api_key, role="model"),
                model=settings.gemini_text_model,
                classifier_model=settings.gemini_classifier_model,
            )
    raise ValueError(f"Unsupported model provider: {provider}")


def _build_model_chain(providers: list[str], settings: Settings) -> ModelProvider:
    instances: list[ModelProvider] = []
    for provider in providers:
        try:
            instance = _build_single_model_provider(provider, settings)
            instances.append(instance)
        except ValueError as exc:
            if _is_local_or_dev(settings):
                raise
            from app.observability.logging import get_logger
            get_logger(__name__).warning(
                "provider_configuration_failure",
                extra={"ctx_role": "model", "ctx_provider": provider, "ctx_error": str(exc)},
            )
    if not instances:
        instances.append(_build_single_model_provider(providers[0] if providers else "mock", settings))
    if len(instances) == 1:
        return instances[0]
    return ModelProviderFallbackWrapper(
        instances,
        role="model",
        attempt_timeout=settings.model_provider_attempt_timeout_seconds,
        circuit_breaker_duration=settings.model_circuit_breaker_duration_seconds,
    )


def _build_single_vision_provider(provider: str, settings: Settings) -> ImageAnalysisProvider:
    match _normalize_provider(provider):
        case "mock":
            return MockVisionPlantIdentificationProvider()
        case "openai":
            return OpenAIVisionProvider(
                api_key=_require_openai_api_key(settings.openai_api_key, role="vision"),
                model=settings.openai_vision_model,
            )
        case "gemini":
            return GeminiVisionProvider(
                api_key=_require_gemini_api_key(settings.gemini_api_key, role="vision"),
                model=settings.gemini_vision_model,
            )
    raise ValueError(f"Unsupported vision provider: {provider}")


def _build_vision_chain(providers: list[str], settings: Settings) -> ImageAnalysisProvider:
    instances: list[ImageAnalysisProvider] = []
    for provider in providers:
        try:
            instance = _build_single_vision_provider(provider, settings)
            instances.append(instance)
        except ValueError as exc:
            if _is_local_or_dev(settings):
                raise
            from app.observability.logging import get_logger
            get_logger(__name__).warning(
                "provider_configuration_failure",
                extra={"ctx_role": "vision", "ctx_provider": provider, "ctx_error": str(exc)},
            )
    if not instances:
        instances.append(_build_single_vision_provider(providers[0] if providers else "mock", settings))
    if len(instances) == 1:
        return instances[0]
    return ImageAnalysisProviderFallbackWrapper(
        instances,
        role="vision",
        attempt_timeout=settings.vision_provider_attempt_timeout_seconds,
        circuit_breaker_duration=settings.vision_circuit_breaker_duration_seconds,
    )


def _build_single_judge_provider(provider: str, settings: Settings) -> JudgeEvaluationProvider:
    match _normalize_provider(provider):
        case "mock":
            return MockModelProvider()
        case "openai":
            return OpenAIJudgeProvider(
                api_key=_require_openai_api_key(settings.openai_api_key, role="judge"),
                model=settings.openai_judge_model,
            )
        case "gemini":
            return GeminiJudgeProvider(
                api_key=_require_gemini_api_key(settings.gemini_api_key, role="judge"),
                model=settings.gemini_judge_model,
            )
    raise ValueError(f"Unsupported judge provider: {provider}")


def _build_judge_chain(providers: list[str], settings: Settings) -> JudgeEvaluationProvider:
    instances: list[JudgeEvaluationProvider] = []
    for provider in providers:
        try:
            instance = _build_single_judge_provider(provider, settings)
            instances.append(instance)
        except ValueError as exc:
            if _is_local_or_dev(settings):
                raise
            from app.observability.logging import get_logger
            get_logger(__name__).warning(
                "provider_configuration_failure",
                extra={"ctx_role": "judge", "ctx_provider": provider, "ctx_error": str(exc)},
            )
    if not instances:
        instances.append(_build_single_judge_provider(providers[0] if providers else "mock", settings))
    if len(instances) == 1:
        return instances[0]
    return JudgeEvaluationProviderFallbackWrapper(
        instances,
        role="judge",
        attempt_timeout=settings.judge_provider_attempt_timeout_seconds,
        circuit_breaker_duration=settings.judge_circuit_breaker_duration_seconds,
    )


def _build_single_search_provider(provider: str, settings: Settings) -> SearchProvider:
    match _normalize_provider(provider):
        case "mock":
            return MockSearchProvider()
        case "openai":
            return OpenAISearchProvider(
                api_key=_require_openai_api_key(settings.openai_api_key, role="search"),
                model=settings.openai_search_model,
            )
        case "gemini":
            return GeminiSearchProvider(
                api_key=_require_gemini_api_key(settings.gemini_api_key, role="search"),
                model=settings.gemini_search_model,
            )
    raise ValueError(f"Unsupported search provider: {provider}")


def _build_search_chain(providers: list[str], settings: Settings) -> SearchProvider:
    instances: list[SearchProvider] = []
    for provider in providers:
        try:
            instance = _build_single_search_provider(provider, settings)
            instances.append(instance)
        except ValueError as exc:
            if _is_local_or_dev(settings):
                raise
            from app.observability.logging import get_logger
            get_logger(__name__).warning(
                "provider_configuration_failure",
                extra={"ctx_role": "search", "ctx_provider": provider, "ctx_error": str(exc)},
            )
    if not instances:
        instances.append(_build_single_search_provider(providers[0] if providers else "mock", settings))
    if len(instances) == 1:
        return instances[0]
    return SearchProviderFallbackWrapper(
        instances,
        role="search",
        attempt_timeout=settings.search_provider_attempt_timeout_seconds,
        circuit_breaker_duration=settings.search_circuit_breaker_duration_seconds,
    )


def _build_embedding_provider(provider: str, settings: Settings) -> EmbeddingProvider:
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


def _build_trefle_provider(provider: str, settings: Settings) -> PlantDataProvider:
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


def _build_perenual_provider(provider: str, settings: Settings) -> PlantDataProvider:
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
