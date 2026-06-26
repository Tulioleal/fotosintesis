from __future__ import annotations

from app.assistant.aspect_metadata import is_safety_sensitive_aspect
from app.assistant.care_contracts import RequiredAspect
from app.assistant.graph.constants import LEGACY_ASPECT_TRANSLATION
from app.assistant.graph.types import AssistantState


def _is_safety_sensitive_question(message: str) -> bool:
    return False


def _has_missing_safety_aspect(state: AssistantState | dict) -> bool:
    translated = [LEGACY_ASPECT_TRANSLATION.get(value, value) for value in state.get("missing_aspects", [])]
    return any(is_safety_sensitive_aspect(value) for value in translated if value in RequiredAspect._value2member_map_)


def _has_requested_safety_aspect(values: list[str]) -> bool:
    translated = [LEGACY_ASPECT_TRANSLATION.get(value, value) for value in values]
    return any(is_safety_sensitive_aspect(value) for value in translated if value in RequiredAspect._value2member_map_)


def _has_relevant_plant_context(state: AssistantState | dict) -> bool:
    if state.get("plant_binomial_name") or state.get("plant_scientific_name"):
        return True
    if state.get("selected_plant") or state.get("operational_plant_name"):
        return True
    retrieval = state.get("retrieval")
    if retrieval is not None and getattr(retrieval, "chunks", None):
        return True
    return bool(state.get("web_results") or state.get("source_support") or state.get("covered_aspects"))

__all__ = [
    "_has_missing_safety_aspect",
    "_has_relevant_plant_context",
    "_has_requested_safety_aspect",
    "_is_safety_sensitive_question",
]
