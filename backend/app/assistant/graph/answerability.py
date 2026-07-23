from __future__ import annotations

import asyncio
from typing import Any

from app.assistant.aspect_metadata import aspect_validation_guidance, is_safety_sensitive_aspect
from app.assistant.care_contracts import EvidenceValidationResult, RequiredAspect
from app.assistant.graph.answers import _append_reason, _log_answerability_decision
from app.assistant.graph.constants import LEGACY_ASPECT_TRANSLATION
from app.assistant.graph.helpers import logger
from app.assistant.graph.plant_resolution import _display_name_for_answer
from app.assistant.graph.types import AnswerabilityResult, AssistantState
from app.assistant.graph_shared import _shorten
from app.assistant.semantic_coverage import CoverageThresholds, SemanticEvidence, semantic_coverage_service
from app.assistant.tools import AssistantTools
from app.knowledge.schemas import KnowledgeChunk
from app.observability.tracing import get_trace_id


ASPECT_VALIDATION_GUIDANCE: dict[str, str] = aspect_validation_guidance(
    [member.value for member in RequiredAspect]
)


def _graph_aspect_validation_guidance(required_aspects: list[str]) -> dict[str, str]:
    return aspect_validation_guidance(required_aspects)


_aspect_validation_guidance = _graph_aspect_validation_guidance


async def _judge_answerability(
    tools: AssistantTools,
    *,
    evidence_type: str,
    question: str,
    plant_name: str | None,
    topic: str,
    evidence: str,
    source_metadata: list[dict],
    required_aspects: list[str] | None = None,
    extra_payload: dict[str, object] | None = None,
    timeout_seconds: float | None = None,
) -> AnswerabilityResult:
    judge = getattr(getattr(tools, "providers", None), "judge", None)
    if judge is None or not hasattr(judge, "judge_response"):
        return AnswerabilityResult(reason="answerability judge provider unavailable")
    payload = {
        "question": question,
        "plant_name": plant_name,
        "topic": topic,
        "required_aspects": required_aspects or [],
        "aspect_validation_guidance": _aspect_validation_guidance(required_aspects or []),
        "evidence_type": evidence_type,
        "evidence": _shorten(evidence, 1800),
        "source_metadata": source_metadata[:5],
    }
    if extra_payload:
        payload.update(extra_payload)
    rubric = {
        "passing_score": 1.0,
        "criteria": [
            "Return full only when the evidence directly answers every requested domain-qualified required aspect in the user's exact question.",
            "Return partial when the evidence directly supports some requested domain-qualified required aspects but leaves others missing.",
            "Return insufficient when evidence is merely about the same plant or general care but misses the asked domain-qualified aspect.",
            "Return contradictory when supplied sources make conflicting claims that prevent a reliable answer.",
            "For toxicity_*, safety_*, taxonomy_*, or diagnosis_* questions, mark those aspects missing unless directly supported by supplied evidence.",
            "Diagnosis answers MUST present causes as hypotheses or possibilities unless source-supported evidence directly identifies the cause for the specific plant and symptom context.",
            "Do not use general model knowledge outside the supplied evidence.",
            "Use aspect_validation_guidance when deciding whether evidence directly covers a required aspect.",
            "Evaluate coverage independently for each requested domain-qualified aspect.",
            "Each source_support item intended for durable ingestion must contain exactly one source URL and an evidence quote taken from that source. Use separate support items when different sources support the same claim.",
        ],
        "expected_output": {
            "status": "one of full, partial, insufficient, contradictory",
            "covered_aspects": "array of required domain-qualified aspect strings directly supported by evidence",
            "missing_aspects": "array of required domain-qualified aspect strings not directly supported by evidence",
            "source_support": "array of objects with claim, source_urls, covered_aspects, evidence_quote, confidence",
            "contradictions": "array of objects with claim_a, claim_b, source_a_urls, source_b_urls",
            "confidence": "0 to 1 score",
            "score": "same numeric value as confidence for compatibility",
            "passed": "true only when status is full",
            "reasons": "short explanations for the status decision",
        },
    }
    logger.info(
        "assistant answerability judge requested",
        extra={
            "ctx_trace_id": get_trace_id(),
            "ctx_evidence_type": evidence_type,
            "ctx_topic": topic,
            "ctx_plant_name_present": bool(plant_name),
            "ctx_required_aspects": required_aspects or [],
            "ctx_source_count": len(source_metadata),
            "ctx_evidence_chars": len(evidence),
            "ctx_has_extra_payload": bool(extra_payload),
        },
    )
    try:
        if timeout_seconds is not None:
            result = await asyncio.wait_for(
                judge.judge_response(payload, rubric), timeout=timeout_seconds
            )
        else:
            result = await judge.judge_response(payload, rubric)
    except (TimeoutError, asyncio.TimeoutError, asyncio.CancelledError):
        return AnswerabilityResult(
            status="insufficient",
            answerable=False,
            reason=f"answerability judge timed out after {timeout_seconds}s",
        )
    except Exception as exc:
        return AnswerabilityResult(reason=f"answerability judge failed: {exc}")
    normalized = _answerability_from_judge_result(result)
    logger.info(
        "assistant answerability judge completed",
        extra={
            "ctx_trace_id": get_trace_id(),
            "ctx_evidence_type": evidence_type,
            "ctx_status": normalized.status,
            "ctx_answerable": normalized.answerable,
            "ctx_covered_aspects": normalized.covered_aspects,
            "ctx_missing_aspects": normalized.missing_aspects,
            "ctx_judge_confidence": normalized.confidence,
            "ctx_source_support_count": len(normalized.source_support),
            "ctx_contradictions_count": len(normalized.contradictions),
            "ctx_reason": normalized.reason,
        },
    )
    return normalized


def _answerability_from_judge_result(result: Any) -> AnswerabilityResult:
    return semantic_coverage_service.map_judge_result(result)


def _validated_answerability(
    result: AnswerabilityResult,
    *,
    requested_aspects: list[str],
    source_metadata: list[dict] | None = None,
) -> AnswerabilityResult:
    return semantic_coverage_service.normalize_answerability(
        result,
        requested_aspects=requested_aspects,
    )


def _normalized_source_support(
    items: list[dict[str, object]],
    *,
    allowed_aspects: list[str],
) -> list[dict[str, object]]:
    return semantic_coverage_service.normalized_source_support(
        items,
        allowed_aspects=allowed_aspects,
    )


def _valid_source_support(item: dict[str, object], requested_aspects: list[str]) -> bool:
    return semantic_coverage_service.valid_source_support(item, requested_aspects)


def _valid_contradiction(item: dict[str, object]) -> bool:
    return semantic_coverage_service.valid_contradiction(item)


def _evidence_from_chunks(chunks: list[KnowledgeChunk]) -> str:
    return " ".join(_shorten(chunk.content, 500) for chunk in chunks[:4])


def _validate_evidence_against_required_aspects(
    state: AssistantState | dict,
    *,
    evidence: str,
    semantic_result: AnswerabilityResult,
    threshold: float,
    safety_threshold: float,
    strong_threshold: float = 0.30,
) -> EvidenceValidationResult:
    requested = _required_aspects_from_state(state)
    candidate_values = (
        [aspect.value for aspect in requested]
        if semantic_result.status == "full" and semantic_result.answerable
        else semantic_result.covered_aspects
    )
    strong_support = _is_strong_full_support(
        semantic_result, [aspect.value for aspect in requested]
    )
    covered = []
    for aspect in requested:
        if aspect.value not in candidate_values:
            continue
        aspect_threshold = _validation_threshold_for_aspect(
            aspect,
            semantic_result,
            [item.value for item in requested],
            default_threshold=threshold,
            strong_threshold=strong_threshold,
            safety_threshold=safety_threshold,
        )
        validated = semantic_result.confidence >= aspect_threshold
        logger.info(
            "assistant threshold decision",
            extra={
                "ctx_trace_id": get_trace_id(),
                "ctx_aspect": aspect.value,
                "ctx_threshold_used": aspect_threshold,
                "ctx_confidence": semantic_result.confidence,
                "ctx_status": semantic_result.status,
                "ctx_answerable": semantic_result.answerable,
                "ctx_strong_full_support": strong_support,
                "ctx_safety_sensitive": is_safety_sensitive_aspect(aspect),
                "ctx_validated": validated,
            },
        )
        if validated:
            covered.append(aspect)
    missing = [aspect for aspect in requested if aspect not in covered]
    return EvidenceValidationResult(
        answerable=not missing and bool(covered),
        covered_aspects=covered,
        missing_aspects=missing,
        unsupported_claims_risk=bool(missing),
        reason=semantic_result.reason,
        confidence=semantic_result.confidence,
    )


def _required_aspects_from_state(state: AssistantState | dict) -> list[RequiredAspect]:
    values = state.get("required_aspects", []) or []
    translated = [LEGACY_ASPECT_TRANSLATION.get(value, value) for value in values]
    aspects = [
        RequiredAspect(value) for value in translated if value in RequiredAspect._value2member_map_
    ]
    return aspects or [RequiredAspect.general_care_summary]


def _is_strong_full_support(
    semantic_result: AnswerabilityResult, requested_aspects: list[str]
) -> bool:
    return semantic_coverage_service.is_strong_full_support(semantic_result, requested_aspects)


def _validation_threshold_for_aspect(
    aspect: RequiredAspect,
    semantic_result: AnswerabilityResult,
    requested_aspects: list[str],
    default_threshold: float,
    strong_threshold: float,
    safety_threshold: float,
) -> float:
    return semantic_coverage_service.validation_threshold_for_aspect(
        aspect,
        semantic_result,
        requested_aspects,
        thresholds=CoverageThresholds(
            default=default_threshold,
            safety=safety_threshold,
            strong_full=strong_threshold,
        ),
    )


def _merge_aspect_values(left: list[str], right: list[str]) -> list[str]:
    return list(dict.fromkeys([*left, *right]))


def _append_evidence_path(state: AssistantState | dict, path: str) -> list[str]:
    return _merge_aspect_values(list(state.get("evidence_path", [])), [path])


async def evaluate_sufficiency(owner, state: AssistantState) -> dict:
    retrieval = state.get("retrieval")
    chunks = getattr(retrieval, "chunks", []) if retrieval else []
    if not chunks:
        requested = state.get("required_aspects", [])
        result = AnswerabilityResult(
            status="insufficient",
            answerable=False,
            missing_aspects=requested,
            reason="retrieval returned no chunks",
        )
        return {
            "sufficient": False,
            "answerability_status": result.status,
            "answerability": result.as_metadata(),
            "missing_aspects": requested,
        }
    result = await _judge_answerability(
        owner.tools,
        evidence_type="rag",
        question=state["message"],
        plant_name=_display_name_for_answer(state),
        topic=state.get("topic") or "care",
        required_aspects=state.get("required_aspects", []),
        evidence=_evidence_from_chunks(chunks),
        source_metadata=state.get("sources", []),
        timeout_seconds=owner.settings.assistant_judge_timeout_seconds,
    )
    evidence = SemanticEvidence(
        text=_evidence_from_chunks(chunks),
        source_metadata=tuple(state.get("sources", [])),
    )
    normalized = semantic_coverage_service.normalized_coverage(
        result,
        required_aspects=_required_aspects_from_state(state),
        thresholds=CoverageThresholds(
            default=owner.settings.assistant_evidence_validation_threshold,
            safety=owner.settings.assistant_safety_validation_threshold,
            strong_full=owner.settings.assistant_strong_answer_validation_threshold,
        ),
        evidence=evidence,
    )
    _log_answerability_decision(
        "rag", result, None if normalized.status == "full" else "rag_not_answerable"
    )
    if normalized.covered_aspects:
        return {
            "sufficient": normalized.status == "full" and normalized.answerable,
            "answerability_status": normalized.status,
            "answerability": normalized.as_metadata(),
            "source_support": normalized.source_support,
            "contradictions": normalized.contradictions,
            "covered_aspects": normalized.covered_aspects,
            "missing_aspects": normalized.missing_aspects,
            "evidence_path": _append_evidence_path(state, "rag"),
        }
    return {
        "sufficient": False,
        "answerability_status": normalized.status,
        "answerability": normalized.as_metadata(),
        "source_support": normalized.source_support,
        "contradictions": normalized.contradictions,
        "covered_aspects": [],
        "missing_aspects": state.get("required_aspects", []),
        "fallback_reasons": _append_reason(state, "rag_not_answerable"),
    }


__all__ = [
    "ASPECT_VALIDATION_GUIDANCE",
    "_answerability_from_judge_result",
    "_append_evidence_path",
    "_aspect_validation_guidance",
    "_evidence_from_chunks",
    "_graph_aspect_validation_guidance",
    "_is_strong_full_support",
    "_judge_answerability",
    "_normalized_source_support",
    "_required_aspects_from_state",
    "_validated_answerability",
    "_validation_threshold_for_aspect",
    "_validate_evidence_against_required_aspects",
    "evaluate_sufficiency",
]
