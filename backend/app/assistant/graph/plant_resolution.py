from __future__ import annotations

import re

from app.assistant.graph.types import AssistantState
from app.knowledge.page_evidence import TrustedPageEvidence
from app.knowledge.plant_data import StructuredPlantEvidence
from app.knowledge.schemas import KnowledgeChunk
from app.providers.types import SearchResult


def operational_plant_name(
    *,
    plant: str | None,
    plant_binomial_name: str | None,
    plant_scientific_name: str | None,
) -> str | None:
    explicit = _normalize_plant_name(plant_binomial_name)
    if explicit:
        return explicit
    derived = _binomial_from_scientific_name(plant_scientific_name)
    if derived:
        return derived
    return _normalize_plant_name(plant_scientific_name)


def display_plant_name(
    *,
    plant: str | None,
    plant_binomial_name: str | None,
    plant_scientific_name: str | None,
) -> str | None:
    return _first_non_blank(plant, plant_scientific_name, plant_binomial_name)


def _first_non_blank(*values: str | None) -> str | None:
    for value in values:
        normalized = _normalize_plant_name(value)
        if normalized:
            return normalized
    return None


def _normalize_plant_name(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


_LATIN_TOKEN_RE = re.compile(r"^[A-Za-z][A-Za-z]{2,}$")


def _binomial_from_scientific_name(value: str | None) -> str | None:
    normalized = _normalize_plant_name(value)
    if not normalized:
        return None
    tokens = normalized.split()
    if len(tokens) < 2:
        return None
    first, second = tokens[0], tokens[1]
    if _LATIN_TOKEN_RE.match(first) and _LATIN_TOKEN_RE.match(second):
        return f"{first} {second}"
    return None


def _operational_name_for_tools(state: AssistantState) -> str | None:
    return operational_plant_name(
        plant=state.get("plant_hint"),
        plant_binomial_name=state.get("plant_binomial_name"),
        plant_scientific_name=state.get("plant_scientific_name"),
    )


def _display_name_for_answer(state: AssistantState | dict) -> str | None:
    selected = state.get("selected_plant")
    return state.get("display_plant_name") or (_display_plant(selected) if selected else None)


def _display_plant(plant: dict) -> str:
    return str(plant.get("nickname") or plant.get("common_name") or plant.get("scientific_name"))


def _has_confirmed_taxonomy_context(state: AssistantState, selected: dict | None) -> bool:
    if state.get("plant_binomial_name") or state.get("plant_scientific_name"):
        return True
    return bool(
        selected and selected.get("id") is not None and _message_confirms_selected_plant(selected, state["message"])
    )


def _taxonomy_context(state: AssistantState | dict, extra_context: str = "") -> str:
    parts = [extra_context] if extra_context else []
    operational = state.get("operational_plant_name")
    display = state.get("display_plant_name")
    scientific = state.get("plant_scientific_name")
    binomial = state.get("plant_binomial_name")
    if operational and operational != display:
        parts.append(f"Operational name for search/API/RAG: {operational}.")
    if scientific and scientific not in {operational, display}:
        parts.append(f"Full scientific name: {scientific}.")
    if binomial and binomial not in {operational, display}:
        parts.append(f"Binomial name: {binomial}.")
    return " ".join(parts)


def _select_plant(garden: list[dict], plant_hint: str | None, message: str) -> tuple[dict | None, bool]:
    haystack = f"{plant_hint or ''} {message}".casefold()
    matches = [
        plant
        for plant in garden
        if any(
            value and str(value).casefold() in haystack
            for value in (
                plant.get("nickname"),
                plant.get("scientific_name"),
                plant.get("common_name"),
            )
        )
    ]
    if len(matches) == 1:
        return matches[0], False
    if len(matches) > 1:
        return None, True
    if plant_hint:
        return {"scientific_name": plant_hint, "id": None}, False
    return (garden[0], False) if len(garden) == 1 else (None, False)


def _message_confirms_selected_plant(plant: dict, message: str) -> bool:
    haystack = message.casefold()
    return any(
        value and str(value).casefold() in haystack
        for value in (plant.get("nickname"), plant.get("scientific_name"), plant.get("common_name"))
    )


def _sources_from_retrieval(retrieval: object) -> list[dict]:
    chunks: list[KnowledgeChunk] = list(getattr(retrieval, "chunks", []) or [])
    sources = []
    seen = set()
    for chunk in chunks:
        if chunk.source_url in seen:
            continue
        seen.add(chunk.source_url)
        sources.append(
            {
                "title": chunk.metadata.get("title") if isinstance(chunk.metadata, dict) else None,
                "url": chunk.source_url,
                "domain": chunk.source_domain,
                "confidence": chunk.confidence,
            }
        )
    return sources


def _sources_from_web_results(
    results: list[TrustedPageEvidence],
    validations: list[dict[str, object]] | None = None,
) -> list[dict]:
    sources = []
    seen = set()
    confidence_by_url = {
        validation["url"]: validation.get("validation_confidence")
        for validation in validations or []
        if isinstance(validation.get("url"), str)
    }
    for evidence in results:
        result = evidence.result
        if result.url in seen:
            continue
        seen.add(result.url)
        sources.append(
            {
                "title": result.title,
                "url": result.url,
                "domain": result.source_domain,
                "confidence": confidence_by_url.get(result.url),
                "evidence_type": "live_web",
                "evidence_source": evidence.evidence_source,
                "fetch_status": evidence.fetch_status,
                "snippet_only": not evidence.has_fetched_content,
                "source_provenance": evidence.validation_status,
            }
        )
    return sources


def _sources_from_structured_evidence(evidence: StructuredPlantEvidence) -> list[dict]:
    return [
        {
            "title": source.title,
            "url": str(source.url),
            "domain": source.source_domain,
            "confidence": evidence.confidence,
            "evidence_type": "structured_api",
        }
        for source in evidence.sources
    ]


def _usable_web_results(
    data: object, *, required_aspects: list[str] | None = None
) -> list[TrustedPageEvidence]:
    if not isinstance(data, list):
        return []
    results: list[TrustedPageEvidence] = []
    for item in data:
        if isinstance(item, TrustedPageEvidence) and item.result.url and item.evidence_text:
            if item.has_fetched_content or _snippet_has_content(item.result.snippet):
                results.append(_with_evidence_lengths(item))
        elif isinstance(item, SearchResult) and item.url and _snippet_has_content(item.snippet):
            results.append(
                TrustedPageEvidence(
                    result=item,
                    fetch_status="snippet_only",
                    snippet_length=len(item.snippet or ""),
                )
            )
    return results


def _with_evidence_lengths(evidence: TrustedPageEvidence) -> TrustedPageEvidence:
    if evidence.snippet_length:
        return evidence
    return TrustedPageEvidence(
        result=evidence.result,
        content=evidence.content,
        error=evidence.error,
        validation_status=evidence.validation_status,
        fetch_status=evidence.fetch_status,
        fetch_error_category=evidence.fetch_error_category,
        fetched_content_length=evidence.fetched_content_length or len(evidence.content or ""),
        snippet_length=len(evidence.result.snippet or ""),
    )


def _snippet_has_content(snippet: str | None) -> bool:
    return bool(snippet and snippet.strip())

__all__ = [
    "_binomial_from_scientific_name",
    "_display_name_for_answer",
    "_display_plant",
    "_first_non_blank",
    "_has_confirmed_taxonomy_context",
    "_message_confirms_selected_plant",
    "_normalize_plant_name",
    "_operational_name_for_tools",
    "_select_plant",
    "_snippet_has_content",
    "_sources_from_retrieval",
    "_sources_from_structured_evidence",
    "_sources_from_web_results",
    "_taxonomy_context",
    "_usable_web_results",
    "_with_evidence_lengths",
    "display_plant_name",
    "operational_plant_name",
]
