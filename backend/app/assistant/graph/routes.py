from __future__ import annotations

from typing import Literal

from app.assistant.graph.safety import _has_missing_safety_aspect, _has_relevant_plant_context
from app.assistant.graph.types import AssistantState


def _is_disclaimed_guidance_eligible(state: AssistantState | dict) -> bool:
    if state.get("sufficient"):
        return False
    retrieval = state.get("retrieval")
    limitations = list(getattr(retrieval, "limitations", []) if retrieval else [])
    if limitations:
        return False
    if not _has_relevant_plant_context(state):
        return False
    if _has_missing_safety_aspect(state):
        return False
    return True


def _route_after_context(state: AssistantState) -> Literal["clarify", "retrieve", "action"]:
    if state.get("unsafe") or state.get("out_of_domain") or state.get("ambiguous"):
        return "clarify"
    if state.get("intent") in {"reminder", "light"}:
        return "action"
    return "retrieve"


def _route_after_sufficiency(state: AssistantState) -> Literal["answer", "fallback"]:
    if state.get("answer"):
        return "answer"
    return "answer" if state.get("sufficient") else "fallback"


def _route_after_web_fallback(state: AssistantState) -> Literal["answer", "clarify"]:
    if state.get("answer") or state.get("web_results"):
        return "answer"
    if state.get("covered_aspects") and not _has_missing_safety_aspect(state):
        return "answer"
    if _is_disclaimed_guidance_eligible(state) or _has_missing_safety_aspect(state):
        return "answer"
    return "clarify"


def _route_after_failure(state: AssistantState) -> Literal["answer", "end"]:
    return "end" if state.get("answer") else "answer"


__all__ = [
    "_is_disclaimed_guidance_eligible",
    "_route_after_context",
    "_route_after_failure",
    "_route_after_sufficiency",
    "_route_after_web_fallback",
]
