from dataclasses import dataclass

from app.core.settings import get_settings
from app.providers.interfaces import EmbeddingProvider, ImageAnalysisProvider, ModelProvider, SearchProvider
from app.providers.mocks import (
    MockEmbeddingProvider,
    MockModelProvider,
    MockSearchProvider,
    MockVisionPlantIdentificationProvider,
)


@dataclass(frozen=True)
class ProviderRegistry:
    model: ModelProvider
    vision: ImageAnalysisProvider
    search: SearchProvider
    embeddings: EmbeddingProvider


def get_provider_registry() -> ProviderRegistry:
    settings = get_settings()

    if settings.provider_profile != "mock":
        raise ValueError(f"Unsupported provider profile: {settings.provider_profile}")

    return ProviderRegistry(
        model=MockModelProvider(),
        vision=MockVisionPlantIdentificationProvider(),
        search=MockSearchProvider(),
        embeddings=MockEmbeddingProvider(),
    )
