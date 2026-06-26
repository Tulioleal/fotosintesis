from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal, TypedDict
from uuid import UUID

from app.observability.logging import get_logger


logger = get_logger(__name__)

INJECTION_PATTERNS = (
    "ignore previous",
    "ignore the instructions",
    "system prompt",
    "developer message",
    "reveal your prompt",
    "omit the rules",
)

LEGACY_ASPECT_TRANSLATION: dict[str, str] = {
    "fertilizer_frequency": "nutrition_feeding_schedule",
    "treatment_action": "pest_treatment_action",
    "temperature_range": "climate_temperature_range",
    "native_range": "taxonomy_native_range",
    "pet_toxicity": "toxicity_pet_safety",
    "human_edibility": "toxicity_human_edibility",
}


@dataclass(frozen=True)
class FallbackResponseDraft:
    intent: str
    answer_language: str
    allowed_facts: list[str] = field(default_factory=list)
    required_points: list[str] = field(default_factory=list)
    prohibited_points: list[str] = field(default_factory=list)
    rendering_constraints: list[str] = field(default_factory=list)


class AssistantState(TypedDict, total=False):
    user_id: UUID
    message: str
    plant_hint: str | None
    plant_binomial_name: str | None
    plant_scientific_name: str | None
    operational_plant_name: str | None
    display_plant_name: str | None
    care_classification: Any
    required_aspects: list[str]
    covered_aspects: list[str]
    missing_aspects: list[str]
    evidence_path: list[str]
    answer_language: str | None
    diagnostics: dict[str, object]
    intent: str
    topic: str
    garden: list[dict]
    selected_plant: dict | None
    ambiguous: bool
    out_of_domain: bool
    unsafe: bool
    retrieval: Any
    web_search_candidates: list[Any]
    web_results: list[Any]
    web_source_validations: list[dict[str, object]]
    web_validation_confidence: float
    plant_data: Any
    sufficient: bool
    answerability_status: str
    answerability: dict[str, object]
    source_support: list[dict[str, object]]
    contradictions: list[dict[str, object]]
    ingestion_claims: list[dict[str, object]]
    sources: list[dict]
    fallback_reasons: list[str]
    answer: str | None
    requires_confirmation: bool
    reminder_suggestion: dict
    reminder_action: str | None
    reminder_recurrence: str | None
    reminder_due_at: datetime | None
    reminder_suggestion_requested: bool
    tool_failures: list[str]
    provider_fallbacks: list[dict]
    total_generation_failure: bool
    generation_failure: Any
    llm_general_guidance_used: bool


@dataclass(frozen=True)
class AnswerabilityResult:
    status: Literal["full", "partial", "insufficient", "contradictory"] = "insufficient"
    answerable: bool = False
    covered_aspects: list[str] = field(default_factory=list)
    missing_aspects: list[str] = field(default_factory=list)
    source_support: list[dict[str, object]] = field(default_factory=list)
    contradictions: list[dict[str, object]] = field(default_factory=list)
    reason: str = "answerability judge did not confirm direct support"
    confidence: float = 0.0

    def as_metadata(self) -> dict[str, object]:
        return {
            "status": self.status,
            "answerable": self.answerable,
            "covered_aspects": self.covered_aspects,
            "missing_aspects": self.missing_aspects,
            "source_support": self.source_support,
            "contradictions": self.contradictions,
            "reason": self.reason,
            "confidence": self.confidence,
        }


def _extract_due_at(message: str) -> datetime | None:
    match = re.search(r"(20\d{2}-\d{2}-\d{2})[ T](\d{2}:\d{2})", message)
    if not match:
        return None
    value = f"{match.group(1)}T{match.group(2)}"
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)


def _shorten(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "..."


def _strip_source_attribution_from_answer(answer: str) -> str:
    answer = re.sub(r"Source-backed:\s*https?://\S*", "", answer)
    answer = re.sub(r"Fuentes:\s*https?://\S*", "", answer)
    answer = re.sub(r"Sources:\s*https?://\S*", "", answer)
    answer = re.sub(r"References:\s*https?://\S*", "", answer)
    answer = re.sub(r"\bFuente\s*\d*:\s*https?://\S*", "", answer, flags=re.IGNORECASE)
    answer = re.sub(r"\bSource\s*\d*:\s*https?://\S*", "", answer, flags=re.IGNORECASE)
    answer = re.sub(r"According to\s+[A-Z][A-Za-z]*(?:\s+[A-Z][A-Za-z]*)*,?\s*", "", answer, flags=re.IGNORECASE)
    answer = re.sub(r"Seg(ú|u)n\s+[A-Z][A-Za-z]*(?:\s+[A-Z][A-Za-z]*)*,?\s*", "", answer, flags=re.IGNORECASE)
    return answer
