from abc import ABC, abstractmethod
from typing import Any

from app.providers.types import (
    EmbeddingResult,
    ImageAnalysisResult,
    JudgeResult,
    JsonGenerationResult,
    SearchResult,
    TextGenerationResult,
)


class TextGenerationProvider(ABC):
    @abstractmethod
    async def generate_text(self, prompt: str, **kwargs: Any) -> TextGenerationResult:
        raise NotImplementedError


class JsonGenerationProvider(ABC):
    @abstractmethod
    async def generate_json(
        self, prompt: str, schema: dict[str, Any], **kwargs: Any
    ) -> JsonGenerationResult:
        raise NotImplementedError


class ImageAnalysisProvider(ABC):
    @abstractmethod
    async def analyze_image(
        self, image: bytes, prompt: str | None = None, **kwargs: Any
    ) -> ImageAnalysisResult:
        raise NotImplementedError


class EmbeddingProvider(ABC):
    @abstractmethod
    async def create_embeddings(self, texts: list[str], **kwargs: Any) -> EmbeddingResult:
        raise NotImplementedError


class JudgeEvaluationProvider(ABC):
    @abstractmethod
    async def judge_response(
        self, payload: dict[str, Any], rubric: dict[str, Any], **kwargs: Any
    ) -> JudgeResult:
        raise NotImplementedError


class SearchProvider(ABC):
    @abstractmethod
    async def search(self, query: str, **kwargs: Any) -> list[SearchResult]:
        raise NotImplementedError


class ModelProvider(TextGenerationProvider, JsonGenerationProvider, JudgeEvaluationProvider, ABC):
    pass
