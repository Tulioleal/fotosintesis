from typing import Any

from app.providers.interfaces import EmbeddingProvider, ImageAnalysisProvider, ModelProvider, SearchProvider
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


class MockModelProvider(ModelProvider):
    provider_name = "mock-model"

    async def generate_text(self, prompt: str, **kwargs: Any) -> TextGenerationResult:
        return TextGenerationResult(
            provider=self.provider_name,
            model="mock-text",
            text=f"Mock response for: {prompt[:80]}",
        )

    async def generate_json(
        self, prompt: str, schema: dict[str, Any], **kwargs: Any
    ) -> JsonGenerationResult:
        return JsonGenerationResult(
            provider=self.provider_name,
            model="mock-json",
            data={"prompt": prompt[:80], "schema_keys": sorted(schema.keys())},
        )

    async def judge_response(
        self, payload: dict[str, Any], rubric: dict[str, Any], **kwargs: Any
    ) -> JudgeResult:
        return JudgeResult(
            provider=self.provider_name,
            model="mock-judge",
            score=1.0,
            passed=True,
            reasons=["Mock judge accepts deterministic local output."],
        )


class MockVisionPlantIdentificationProvider(ImageAnalysisProvider):
    provider_name = "mock-vision-plant-identification"

    async def analyze_image(
        self, image: bytes, prompt: str | None = None, **kwargs: Any
    ) -> ImageAnalysisResult:
        return ImageAnalysisResult(
            provider=self.provider_name,
            model="mock-vision",
            description="Mock visual analysis detected a compact succulent-like plant.",
            candidates=[
                PlantCandidate(
                    scientific_name="Cotyledon tomentosa",
                    common_name="Pata de oso",
                    confidence_label=ConfidenceLabel.medium,
                    visible_traits=["hojas carnosas", "crecimiento compacto"],
                    provider=self.provider_name,
                )
            ],
            metadata={"image_size_bytes": len(image), "prompt": prompt},
        )


class MockSearchProvider(SearchProvider):
    provider_name = "mock-search"

    async def search(self, query: str, **kwargs: Any) -> list[SearchResult]:
        return [
            SearchResult(
                title="Mock trusted botanical result",
                url="https://example.org/mock-botanical-source",
                snippet=f"Deterministic search result for {query[:80]}",
                source_domain="example.org",
            )
        ]


class MockEmbeddingProvider(EmbeddingProvider):
    provider_name = "mock-embedding"

    async def create_embeddings(self, texts: list[str], **kwargs: Any) -> EmbeddingResult:
        embeddings = [[float((ord(char) % 31) / 31) for char in text[:8]] for text in texts]
        return EmbeddingResult(provider=self.provider_name, model="mock-embedding", embeddings=embeddings)
