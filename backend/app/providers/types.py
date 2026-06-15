from enum import Enum
from typing import Any, Literal

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
    status: Literal["full", "partial", "insufficient", "contradictory"] = "insufficient"
    covered_aspects: list[str] = Field(default_factory=list)
    missing_aspects: list[str] = Field(default_factory=list)
    source_support: list[dict[str, Any]] = Field(default_factory=list)
    contradictions: list[dict[str, Any]] = Field(default_factory=list)
    confidence: float = 0.0

    @classmethod
    def from_provider_data(
        cls,
        *,
        provider: str,
        model: str | None,
        data: dict[str, Any],
        passing_score: float = 1.0,
    ) -> "JudgeResult":
        score = _float_or_zero(data.get("score", data.get("confidence", 0)))
        status = _judge_status(data.get("status"))
        if status is None:
            passed_value = data.get("passed")
            passed = bool(passed_value) if passed_value is not None else score >= passing_score
            status = "full" if passed else "insufficient"
        else:
            passed = status == "full"
            if "passed" in data:
                passed = bool(data.get("passed"))
        confidence = max(0.0, min(1.0, _float_or_zero(data.get("confidence", score))))
        reasons = _string_list(data.get("reasons"))
        reason = str(data.get("reason") or "").strip()
        if reason:
            reasons.append(reason)
        return cls(
            provider=provider,
            model=model,
            score=score,
            passed=passed,
            reasons=list(dict.fromkeys(reasons)),
            status=status,
            covered_aspects=_string_list(data.get("covered_aspects")),
            missing_aspects=_string_list(data.get("missing_aspects")),
            source_support=_dict_list(data.get("source_support")),
            contradictions=_dict_list(data.get("contradictions")),
            confidence=confidence,
        )


class SearchResult(BaseModel):
    title: str
    url: str
    snippet: str
    source_domain: str


class PlantDataResult(ProviderResponse):
    scientific_name: str
    common_name: str | None = None
    family: str | None = None
    genus: str | None = None
    rank: str | None = None
    fields: dict[str, Any] = Field(default_factory=dict)
    source_url: str


def _judge_status(value: Any) -> Literal["full", "partial", "insufficient", "contradictory"] | None:
    status = str(value or "").strip().lower()
    if status == "full":
        return "full"
    if status == "partial":
        return "partial"
    if status == "insufficient":
        return "insufficient"
    if status == "contradictory":
        return "contradictory"
    return None


def _float_or_zero(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, list | tuple | set):
        return [str(item) for item in value if str(item).strip()]
    return []


def _dict_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list | tuple):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]
