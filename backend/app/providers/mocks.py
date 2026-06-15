from typing import Any

from app.providers.interfaces import (
    EmbeddingProvider,
    ImageAnalysisProvider,
    ModelProvider,
    PlantDataProvider,
    SearchProvider,
)
from app.providers.types import (
    ConfidenceLabel,
    EmbeddingResult,
    ImageAnalysisResult,
    JudgeResult,
    JsonGenerationResult,
    PlantDataResult,
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
            status="full",
            confidence=1.0,
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


class MockTreflePlantDataProvider(PlantDataProvider):
    provider_name = "mock-trefle"

    def __init__(self, *, mode: str = "botanical") -> None:
        self.mode = mode
        self.calls: list[str] = []

    async def lookup(self, scientific_name: str, **kwargs: Any) -> PlantDataResult | None:
        self.calls.append(scientific_name)
        if self.mode == "unavailable":
            return None
        fields = {
            "description": f"{scientific_name} is a succulent species with compact growth.",
            "family": "Crassulaceae",
            "genus": scientific_name.split()[0] if scientific_name else None,
        }
        if self.mode == "care":
            fields.update(
                {
                    "watering": "Water moderately only after the substrate dries.",
                    "sunlight": "Provide bright light with protection from harsh afternoon sun.",
                    "soil": "Use a fast-draining succulent substrate.",
                    "care": "Avoid standing water and keep the crown dry.",
                }
            )
        return PlantDataResult(
            provider=self.provider_name,
            model="mock-plant-data",
            scientific_name=scientific_name,
            common_name="Bear paw succulent",
            family="Crassulaceae",
            genus=scientific_name.split()[0] if scientific_name else None,
            rank="species",
            fields={key: value for key, value in fields.items() if value},
            source_url="https://trefle.io/mock/species/cotyledon-tomentosa",
        )


class MockPerenualPlantDataProvider(PlantDataProvider):
    provider_name = "mock-perenual"

    def __init__(self, *, mode: str = "care") -> None:
        self.mode = mode
        self.calls: list[str] = []

    async def lookup(self, scientific_name: str, **kwargs: Any) -> PlantDataResult | None:
        self.calls.append(scientific_name)
        if self.mode == "unavailable":
            return None
        return PlantDataResult(
            provider=self.provider_name,
            model="mock-plant-care",
            scientific_name=scientific_name,
            common_name="Bear paw succulent",
            fields={
                "watering": "Let soil dry between waterings.",
                "sunlight": "Bright indirect light to gentle direct sun.",
                "soil": "Well-draining sandy or succulent mix.",
                "maintenance": "Remove dead leaves and avoid overwatering.",
                "pests": "Watch for mealybugs and scale.",
                "care": "Use containers with drainage holes.",
            },
            source_url="https://perenual.com/mock/species/cotyledon-tomentosa",
        )
