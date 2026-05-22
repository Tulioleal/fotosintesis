from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ConfidenceLabel(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"
    inconclusive = "inconclusive"


class ProviderResponse(BaseModel):
    provider: str
    model: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TextGenerationResult(ProviderResponse):
    text: str


class JsonGenerationResult(ProviderResponse):
    data: dict[str, Any]


class PlantCandidate(BaseModel):
    scientific_name: str
    common_name: str | None = None
    confidence_label: ConfidenceLabel = ConfidenceLabel.inconclusive
    confidence_score: float | None = None
    visible_traits: list[str] = Field(default_factory=list)
    provider: str = "mock"
    needs_user_confirmation: bool = True


class ImageAnalysisResult(ProviderResponse):
    description: str
    candidates: list[PlantCandidate] = Field(default_factory=list)


class EmbeddingResult(ProviderResponse):
    embeddings: list[list[float]]


class JudgeResult(ProviderResponse):
    score: float
    passed: bool
    reasons: list[str] = Field(default_factory=list)


class SearchResult(BaseModel):
    title: str
    url: str
    snippet: str
    source_domain: str
