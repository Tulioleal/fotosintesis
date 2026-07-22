from __future__ import annotations

import asyncio

from app.assistant.aspect_metadata import aspect_query_terms
from app.assistant.care_contracts import RequiredAspect
from app.assistant.graph import answerability
from app.assistant.graph.answers import _append_reason, _log_fallback_route
from app.assistant.graph.constants import LEGACY_ASPECT_TRANSLATION
from app.assistant.graph.helpers import logger
from app.assistant.graph.plant_resolution import (
    _display_name_for_answer,
    _operational_name_for_tools,
    _snippet_has_content,
    _sources_from_web_results,
    _usable_web_results,
)
from app.assistant.graph.types import AnswerabilityResult, AssistantState
from app.assistant.graph_shared import _shorten
from app.assistant.tools import AssistantTools
from app.core.settings import Settings
from app.knowledge.page_evidence import TrustedPageEvidence
from app.observability.tracing import get_trace_id
from app.providers.types import SearchResult


async def _judge_combined_evidence(
    tools: AssistantTools,
    settings: Settings,
    state: AssistantState,
    results: list[TrustedPageEvidence],
) -> AnswerabilityResult:
    requested_values = _final_required_aspect_values(state)
    rag = state.get("retrieval")
    rag_chunks = getattr(rag, "chunks", []) if rag else []
    web_evidence = " ".join(_shorten(result.evidence_text, 700) for result in results[:3])
    combined = " ".join(part for part in (answerability._evidence_from_chunks(rag_chunks), web_evidence) if part.strip())
    source_metadata = state.get("sources", []) + _sources_from_web_results(results[:3])
    _log_combined_judge_evidence(
        evidence_type="combined_rag_web",
        results=results,
        evidence=combined,
        source_count=len(source_metadata),
    )
    semantic = await answerability._judge_answerability(
        tools,
        evidence_type="combined_rag_web",
        question=state["message"],
        plant_name=_display_name_for_answer(state),
        topic=state.get("topic") or "care",
        required_aspects=requested_values,
        evidence=combined,
        source_metadata=source_metadata,
        extra_payload={"rag_answerability": state.get("answerability", {})},
        timeout_seconds=settings.assistant_judge_timeout_seconds,
    )
    if semantic.status == "full" and semantic.answerable:
        covered_values = _safety_constrained_covered_aspects(requested_values, combined)
        semantic = AnswerabilityResult(
            status="full" if set(covered_values) >= set(requested_values) else "partial",
            answerable=set(covered_values) >= set(requested_values),
            covered_aspects=covered_values,
            missing_aspects=[aspect for aspect in requested_values if aspect not in covered_values],
            source_support=semantic.source_support,
            contradictions=semantic.contradictions,
            reason=semantic.reason,
            confidence=semantic.confidence,
        )
    validated = answerability._validated_answerability(
        semantic,
        requested_aspects=requested_values,
        source_metadata=source_metadata,
    )
    if (
        validated.status in {"full", "partial"}
        and validated.confidence < settings.assistant_evidence_validation_threshold
        and _has_requested_safety_aspect(requested_values)
    ):
        validated = AnswerabilityResult(
            status="insufficient",
            answerable=False,
            missing_aspects=requested_values,
            reason="combined safety evidence confidence below validation threshold",
            confidence=validated.confidence,
        )
    logger.info(
        "assistant combined evidence judge evaluated",
        extra={
            "ctx_trace_id": get_trace_id(),
            "ctx_required_aspects": requested_values,
            "ctx_rag_chunk_count": len(rag_chunks),
            "ctx_web_result_count": len(results),
            "ctx_source_count": len(source_metadata),
            "ctx_semantic_status": semantic.status,
            "ctx_validated_status": validated.status,
            "ctx_validated_confidence": validated.confidence,
            "ctx_validated_missing_aspects": validated.missing_aspects,
        },
    )
    return validated


def _safety_constrained_covered_aspects(requested_values: list[str], evidence: str) -> list[str]:
    covered = list(requested_values)
    normalized = evidence.casefold()
    for aspect_value in {
        RequiredAspect.toxicity_pet_safety.value,
        RequiredAspect.toxicity_child_safety.value,
        RequiredAspect.toxicity_human_edibility.value,
    }:
        if aspect_value in covered and not _is_safety_sensitive_question(normalized):
            covered.remove(aspect_value)
    return covered


def _requested_web_aspects(state: AssistantState | dict) -> list[RequiredAspect]:
    values = state.get("missing_aspects") or state.get("required_aspects", [])
    translated = [LEGACY_ASPECT_TRANSLATION.get(value, value) for value in values]
    return [RequiredAspect(aspect) for aspect in translated if aspect in RequiredAspect._value2member_map_]


def _final_required_aspect_values(state: AssistantState | dict) -> list[str]:
    values = state.get("required_aspects") or state.get("missing_aspects", [])
    translated = [LEGACY_ASPECT_TRANSLATION.get(str(value), str(value)) for value in values]
    requested = [aspect for aspect in translated if aspect in RequiredAspect._value2member_map_]
    return requested or [RequiredAspect.general_care_summary.value]


def _combined_answer_evidence(state: AssistantState | dict, web_results: list[TrustedPageEvidence]) -> str:
    parts = [_supported_rag_evidence(state)]
    parts.append(" ".join(_shorten(result.evidence_text, 500) for result in web_results[:3]))
    return " ".join(part for part in parts if part.strip())


def _supported_rag_evidence(state: AssistantState | dict) -> str:
    supported_urls = _source_support_urls(list(state.get("source_support", [])))
    if not supported_urls:
        return ""
    rag = state.get("retrieval")
    chunks = list(getattr(rag, "chunks", []) or []) if rag else []
    supported_chunks = [chunk for chunk in chunks if chunk.source_url in supported_urls]
    return " ".join(_shorten(chunk.content, 500) for chunk in supported_chunks[:3])


def _web_source_validation_metadata_from_result(result: AnswerabilityResult) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for support in result.source_support:
        urls = support.get("source_urls")
        if not isinstance(urls, list):
            continue
        for url in urls:
            if isinstance(url, str) and url.strip():
                rows.append(
                    {
                        "url": url,
                        "covered_aspects": list(support.get("covered_aspects", [])) if isinstance(support.get("covered_aspects"), list) else [],
                        "missing_aspects": result.missing_aspects,
                        "validation_confidence": support.get("confidence", result.confidence),
                    }
                )
    return rows


def _source_support_urls(source_support: list[dict[str, object]]) -> set[str]:
    urls: set[str] = set()
    for support in source_support:
        raw_urls = support.get("source_urls")
        if isinstance(raw_urls, list):
            urls.update(str(url) for url in raw_urls if str(url).strip())
    return urls


def _targeted_web_query(scientific_name: str, missing_aspects: list[str], topic: str, question: str) -> str:
    metadata_terms = aspect_query_terms(missing_aspects)
    aspect_text = " ".join(metadata_terms) if metadata_terms else topic
    return f"{scientific_name} {aspect_text} {_web_query_question_context(question)} houseplant care trusted source"


def _reusable_web_search_candidates(state: AssistantState | dict) -> list[SearchResult]:
    candidates = list(state.get("web_search_candidates", []) or [])
    if candidates:
        return candidates
    retrieval = state.get("retrieval")
    if retrieval is None:
        return []
    return list(getattr(retrieval, "search_candidates", []) or [])


def _candidate_results_from_web_data(data: object) -> list[SearchResult]:
    if not isinstance(data, list):
        return []
    results: list[SearchResult] = []
    for item in data:
        if isinstance(item, TrustedPageEvidence):
            results.append(item.result)
        elif isinstance(item, SearchResult):
            results.append(item)
    return results


def _log_web_fallback_query(
    state: AssistantState | dict,
    *,
    scientific_name: str,
    query: str,
    missing_aspects: list[str],
    reused: bool,
) -> None:
    logger.info(
        "assistant web fallback query prepared",
        extra={
            "ctx_trace_id": get_trace_id(),
            "ctx_scientific_name": scientific_name,
            "ctx_topic": state.get("topic") or "care",
            "ctx_required_aspects": list(state.get("required_aspects", [])),
            "ctx_missing_aspects": list(missing_aspects),
            "ctx_query": query,
            "ctx_reused_candidates": reused,
        },
    )


def _log_web_search_candidates(results: list[SearchResult], *, reused: bool) -> None:
    logger.info(
        "assistant web search candidates selected",
        extra={
            "ctx_trace_id": get_trace_id(),
            "ctx_candidate_count": len(results),
            "ctx_reused_candidates": reused,
            "ctx_candidates": [
                {
                    "url": result.url,
                    "domain": result.source_domain,
                    "snippet_length": len(result.snippet or ""),
                    "snippet_source": result.metadata.get("snippet_source") if isinstance(result.metadata, dict) else None,
                }
                for result in results[:5]
            ],
        },
    )


def _log_web_evidence_selection(results: list[TrustedPageEvidence], *, required_aspects: list[str]) -> None:
    logger.info(
        "assistant web evidence selected",
        extra={
            "ctx_trace_id": get_trace_id(),
            "ctx_required_aspects": list(required_aspects),
            "ctx_result_count": len(results),
            "ctx_fetched_content_count": sum(1 for result in results if result.has_fetched_content),
            "ctx_snippet_only_count": sum(1 for result in results if not result.has_fetched_content),
            "ctx_results": [
                {
                    "url": result.result.url,
                    "domain": result.result.source_domain,
                    "evidence_source": result.evidence_source,
                    "fetch_status": result.fetch_status,
                    "fetch_error_category": result.fetch_error_category,
                    "fetched_content_length": result.fetched_content_length,
                    "snippet_length": result.snippet_length or len(result.result.snippet or ""),
                }
                for result in results[:5]
            ],
        },
    )


def _log_combined_judge_evidence(*, evidence_type: str, results: list[TrustedPageEvidence], evidence: str, source_count: int) -> None:
    logger.info(
        "assistant web judge evidence prepared",
        extra={
            "ctx_trace_id": get_trace_id(),
            "ctx_evidence_type": evidence_type,
            "ctx_fetched_content_count": sum(1 for result in results if result.has_fetched_content),
            "ctx_snippet_only_count": sum(1 for result in results if not result.has_fetched_content),
            "ctx_evidence_chars": len(evidence),
            "ctx_source_count": source_count,
        },
    )


def _web_query_question_context(question: str) -> str:
    normalized = " ".join(question.split())
    return _shorten(normalized, 120) if normalized else ""


def _validated_web_metadata(state: AssistantState, results: list[TrustedPageEvidence]) -> dict[str, object]:
    domains = [item.result.source_domain for item in results if item.result.source_domain]
    return {
        "topic": state.get("topic") or "care",
        "required_aspects": list(state.get("required_aspects", [])),
        "covered_aspects": list(state.get("covered_aspects", [])),
        "language": state.get("answer_language") or "es",
        "evidence_type": "validated_web",
        "validation_confidence": state.get("web_validation_confidence", 0.0),
        "source_domain": domains[0] if domains else None,
        "review_status": "auto_ingested",
        "source_validations": list(state.get("web_source_validations", [])),
    }


def _validated_claim_payloads(
    state: AssistantState,
    *,
    scientific_name: str,
    topic: str,
) -> list[dict[str, object]]:
    status = str(state.get("answerability_status") or "")
    if status not in {"full", "partial"}:
        return []
    payloads: list[dict[str, object]] = []
    sources_by_url = {str(source.get("url")): source for source in state.get("sources", []) if source.get("url")}
    final_covered = {
        str(aspect)
        for aspect in state.get("covered_aspects", [])
        if isinstance(aspect, str)
    }
    for support in state.get("source_support", []):
        urls = support.get("source_urls")
        aspects = support.get("covered_aspects")
        claim = str(support.get("claim") or "").strip()
        if not claim or not isinstance(urls, list) or not isinstance(aspects, list):
            continue
        normalized_aspects = list(
            dict.fromkeys(
                str(aspect)
                for aspect in aspects
                if isinstance(aspect, str) and aspect in final_covered
            )
        )
        if not normalized_aspects:
            continue

        raw_quote = support.get("evidence_quote")
        if not isinstance(raw_quote, str):
            continue
        evidence_quote = raw_quote.strip()
        if not evidence_quote:
            continue

        valid_urls = list(
            dict.fromkeys(
                url.strip()
                for url in urls
                if isinstance(url, str) and url.strip()
            )
        )
        if len(valid_urls) != 1:
            continue
        url = valid_urls[0]
        source = sources_by_url.get(url, {})
        source_provenance = source.get("source_provenance")
        if source_provenance not in {"trusted", "external_fallback"}:
            continue
        payloads.append(
            {
                "scientific_name": scientific_name,
                "topic": topic,
                "required_aspects": list(state.get("required_aspects", [])),
                "covered_aspects": normalized_aspects,
                "missing_aspects": list(state.get("missing_aspects", [])),
                "answerability_status": status,
                "claim": claim,
                "evidence_quote": evidence_quote,
                "source_url": url,
                "source_title": source.get("title"),
                "source_domain": source.get("domain"),
                "source_provenance": source_provenance,
                "confidence": float(support.get("confidence", state.get("web_validation_confidence", 0.0)) or 0.0),
                "language": state.get("answer_language") or "es",
            }
        )
    return payloads


def _has_requested_safety_aspect(values: list[str]) -> bool:
    translated = [LEGACY_ASPECT_TRANSLATION.get(value, value) for value in values]
    return any(value.startswith(("toxicity_", "safety_")) for value in translated)


def _is_safety_sensitive_question(message: str) -> bool:
    return False


async def fallback_web_search(owner, state: AssistantState) -> dict:
    scientific_name = _operational_name_for_tools(state)
    if not scientific_name:
        return {}
    missing_aspects = state.get("missing_aspects") or state.get("required_aspects", [])
    query = _targeted_web_query(scientific_name, missing_aspects, state.get("topic") or "care", state["message"])
    reusable_candidates = _reusable_web_search_candidates(state)
    _log_web_fallback_query(state, scientific_name=scientific_name, query=query, missing_aspects=missing_aspects, reused=bool(reusable_candidates))
    fallback_reasons = _append_reason(state, "web_search_used")
    _log_fallback_route("web_search_used", evidence_type="web")
    try:
        result = await asyncio.wait_for(
            owner.tools.trusted_web_search(query, candidates=reusable_candidates or None),
            timeout=owner.settings.assistant_web_search_timeout_seconds,
        )
    except (TimeoutError, asyncio.TimeoutError, asyncio.CancelledError):
        return {
            "tool_failures": state.get("tool_failures", []) + [f"trusted_web_search timed out after {owner.settings.assistant_web_search_timeout_seconds}s"],
            "fallback_reasons": fallback_reasons,
        }
    if not result.ok:
        return {"tool_failures": state.get("tool_failures", []) + [result.error or "trusted_web_search failed"], "fallback_reasons": fallback_reasons}
    selected_candidates = _candidate_results_from_web_data(result.data)
    _log_web_search_candidates(selected_candidates, reused=bool(reusable_candidates))
    web_results = _usable_web_results(result.data, required_aspects=missing_aspects)
    _log_web_evidence_selection(web_results, required_aspects=missing_aspects)
    if not web_results:
        empty_result = AnswerabilityResult(
            status="insufficient",
            answerable=False,
            missing_aspects=state.get("missing_aspects") or state.get("required_aspects", []),
            reason="trusted web search returned no usable evidence",
        )
        return {
            "answerability_status": empty_result.status,
            "answerability": empty_result.as_metadata(),
            "source_support": empty_result.source_support,
            "contradictions": empty_result.contradictions,
            "fallback_reasons": _append_reason({**state, "fallback_reasons": fallback_reasons}, "web_search_no_direct_answer"),
        }
    requested_web_aspects = _requested_web_aspects(state)
    final_result = await _judge_combined_evidence(owner.tools, owner.settings, state, web_results)
    supported_urls = {url for support in final_result.source_support for url in support.get("source_urls", []) if isinstance(url, str)}
    validated_web_results = [result for result in web_results if not supported_urls or result.result.url in supported_urls]
    web_source_validations = _web_source_validation_metadata_from_result(final_result)
    if final_result.status not in {"full", "partial", "contradictory"} or not validated_web_results:
        return {
            "answerability_status": final_result.status,
            "answerability": final_result.as_metadata(),
            "source_support": final_result.source_support,
            "contradictions": final_result.contradictions,
            "missing_aspects": final_result.missing_aspects or [aspect.value for aspect in requested_web_aspects],
            "fallback_reasons": _append_reason({**state, "fallback_reasons": fallback_reasons}, "web_search_not_validated"),
        }
    return {
        "web_results": validated_web_results,
        "web_source_validations": web_source_validations,
        "sources": state.get("sources", []) + _sources_from_web_results(validated_web_results, web_source_validations),
        "fallback_reasons": fallback_reasons,
        "answerability_status": final_result.status,
        "answerability": final_result.as_metadata(),
        "source_support": final_result.source_support,
        "contradictions": final_result.contradictions,
        "covered_aspects": final_result.covered_aspects,
        "missing_aspects": final_result.missing_aspects,
        "evidence_path": answerability._append_evidence_path(state, "web"),
        "web_validation_confidence": final_result.confidence,
    }


__all__ = [
    "_candidate_results_from_web_data",
    "_combined_answer_evidence",
    "_final_required_aspect_values",
    "_judge_combined_evidence",
    "_log_combined_judge_evidence",
    "_log_web_evidence_selection",
    "_log_web_fallback_query",
    "_log_web_search_candidates",
    "_requested_web_aspects",
    "_reusable_web_search_candidates",
    "_snippet_has_content",
    "_source_support_urls",
    "_supported_rag_evidence",
    "_targeted_web_query",
    "_validated_claim_payloads",
    "_validated_web_metadata",
    "_web_query_question_context",
    "_web_source_validation_metadata_from_result",
    "fallback_web_search",
]
