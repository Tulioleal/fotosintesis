from __future__ import annotations

import asyncio
from typing import Any, Literal

from app.assistant.aspect_metadata import aspect_validation_guidance, is_safety_sensitive_aspect
from app.assistant.care_contracts import EvidenceValidationResult, RequiredAspect
from app.assistant.graph.answers import _append_reason, _log_answerability_decision
from app.assistant.graph.constants import LEGACY_ASPECT_TRANSLATION
from app.assistant.graph.helpers import logger
from app.assistant.graph.plant_resolution import _display_name_for_answer
from app.assistant.graph.types import AnswerabilityResult, AssistantState
from app.assistant.graph_shared import _shorten
from app.assistant.tools import AssistantTools
from app.knowledge.schemas import KnowledgeChunk
from app.observability.tracing import get_trace_id


ASPECT_VALIDATION_GUIDANCE: dict[str, str] = aspect_validation_guidance([member.value for member in RequiredAspect])


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
            result = await asyncio.wait_for(judge.judge_response(payload, rubric), timeout=timeout_seconds)
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
    score = _float_or_zero(getattr(result, "score", 0.0))
    confidence = max(0.0, min(1.0, _float_or_zero(getattr(result, "confidence", score))))
    reasons = [str(reason) for reason in getattr(result, "reasons", []) if str(reason).strip()]
    status = _answerability_status(getattr(result, "status", None))
    if status is None:
        status = "full" if bool(getattr(result, "passed", False)) else "insufficient"
    answerable = status == "full"
    if hasattr(result, "answerable"):
        answerable = bool(getattr(result, "answerable"))
    return AnswerabilityResult(
        status=status,
        answerable=answerable,
        covered_aspects=_string_list(getattr(result, "covered_aspects", [])),
        missing_aspects=[] if status == "full" else _string_list(getattr(result, "missing_aspects", [])),
        source_support=_dict_list(getattr(result, "source_support", [])),
        contradictions=_dict_list(getattr(result, "contradictions", [])),
        reason="; ".join(reasons) if reasons else "answerability judge did not provide a reason",
        confidence=confidence,
    )


def _answerability_status(value: Any) -> Literal["full", "partial", "insufficient", "contradictory"] | None:
    status = str(value or "").strip().lower()
    if status in {"full", "partial", "insufficient", "contradictory"}:
        return status
    return None


def _string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, list | tuple | set):
        return [str(item) for item in value if str(item).strip()]
    return []


def _dict_list(value: Any) -> list[dict[str, object]]:
    if not isinstance(value, list | tuple):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def _validated_answerability(
    result: AnswerabilityResult,
    *,
    requested_aspects: list[str],
    source_metadata: list[dict] | None = None,
) -> AnswerabilityResult:
    if result.answerable and result.status == "insufficient":
        result = AnswerabilityResult(
            status="full",
            answerable=True,
            covered_aspects=result.covered_aspects,
            missing_aspects=result.missing_aspects,
            source_support=result.source_support,
            contradictions=result.contradictions,
            reason=result.reason,
            confidence=result.confidence,
        )
    requested = [aspect for aspect in requested_aspects if aspect]
    covered = [aspect for aspect in result.covered_aspects if aspect in requested]
    missing = [aspect for aspect in requested if aspect not in covered]
    support = [item for item in result.source_support if _valid_source_support(item, requested)]
    contradictions = [item for item in result.contradictions if _valid_contradiction(item)]
    if result.status == "full":
        if not requested:
            requested = [RequiredAspect.general_care_summary.value]
            covered = requested if result.answerable else covered
            missing = [] if result.answerable else requested
        if result.answerable and not covered:
            covered = list(requested)
            missing = []
        if set(covered) >= set(requested) and support:
            return AnswerabilityResult("full", True, covered, [], support, contradictions, result.reason, result.confidence)
        if covered and support:
            return AnswerabilityResult("partial", False, covered, missing, support, contradictions, result.reason, result.confidence)
        return AnswerabilityResult("insufficient", False, [], requested, reason=result.reason, confidence=result.confidence)
    if result.status == "partial":
        if set(covered) >= set(requested) and support and not contradictions:
            return AnswerabilityResult("full", True, covered, [], support, contradictions, result.reason, result.confidence)
        if covered and support:
            return AnswerabilityResult("partial", False, covered, missing, support, contradictions, result.reason, result.confidence)
        return AnswerabilityResult("insufficient", False, [], requested, reason=result.reason, confidence=result.confidence)
    if result.status == "contradictory":
        if contradictions:
            return AnswerabilityResult("contradictory", False, covered, missing or requested, support, contradictions, result.reason, result.confidence)
        return AnswerabilityResult(
            "insufficient",
            False,
            covered,
            missing or requested,
            support,
            reason=result.reason or "contradictory answerability result lacked source URLs",
            confidence=result.confidence,
        )
    return AnswerabilityResult("insufficient", False, covered, missing or requested, support, contradictions, result.reason, result.confidence)


def _valid_source_support(item: dict[str, object], requested_aspects: list[str]) -> bool:
    urls = item.get("source_urls")
    aspects = item.get("covered_aspects")
    quote = item.get("evidence_quote")
    return (
        isinstance(item.get("claim"), str)
        and bool(str(item.get("claim")).strip())
        and isinstance(quote, str)
        and bool(quote.strip())
        and isinstance(urls, list)
        and any(isinstance(url, str) and url.strip() for url in urls)
        and isinstance(aspects, list)
        and any(isinstance(aspect, str) and aspect in requested_aspects for aspect in aspects)
    )


def _valid_contradiction(item: dict[str, object]) -> bool:
    left = item.get("source_a_urls")
    right = item.get("source_b_urls")
    return (
        isinstance(item.get("claim_a"), str)
        and isinstance(item.get("claim_b"), str)
        and isinstance(left, list)
        and isinstance(right, list)
        and any(isinstance(url, str) and url.strip() for url in left)
        and any(isinstance(url, str) and url.strip() for url in right)
    )


def _float_or_zero(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


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
    candidate_values = [aspect.value for aspect in requested] if semantic_result.status == "full" and semantic_result.answerable else semantic_result.covered_aspects
    strong_support = _is_strong_full_support(semantic_result, [aspect.value for aspect in requested])
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
    aspects = [RequiredAspect(value) for value in translated if value in RequiredAspect._value2member_map_]
    return aspects or [RequiredAspect.general_care_summary]


def _is_strong_full_support(semantic_result: AnswerabilityResult, requested_aspects: list[str]) -> bool:
    return (
        semantic_result.status == "full"
        and semantic_result.answerable
        and bool(semantic_result.source_support)
        and not semantic_result.contradictions
        and all(aspect in set(semantic_result.covered_aspects) for aspect in requested_aspects)
    )


def _validation_threshold_for_aspect(
    aspect: RequiredAspect,
    semantic_result: AnswerabilityResult,
    requested_aspects: list[str],
    default_threshold: float,
    strong_threshold: float,
    safety_threshold: float,
) -> float:
    if is_safety_sensitive_aspect(aspect):
        return safety_threshold
    if _is_strong_full_support(semantic_result, requested_aspects):
        return strong_threshold
    return default_threshold


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
    requested = state.get("required_aspects", [])
    result = _validated_answerability(
        result,
        requested_aspects=requested,
        source_metadata=state.get("sources", []),
    )
    _log_answerability_decision("rag", result, None if result.status == "full" else "rag_not_answerable")
    validation = _validate_evidence_against_required_aspects(
        state,
        evidence=_evidence_from_chunks(chunks),
        semantic_result=result,
        threshold=owner.settings.assistant_evidence_validation_threshold,
        safety_threshold=owner.settings.assistant_safety_validation_threshold,
        strong_threshold=owner.settings.assistant_strong_answer_validation_threshold,
    )
    if validation.covered_aspects:
        return {
            "sufficient": result.status == "full" and validation.answerable,
            "answerability_status": result.status,
            "answerability": result.as_metadata(),
            "source_support": result.source_support,
            "contradictions": result.contradictions,
            "covered_aspects": [aspect.value for aspect in validation.covered_aspects],
            "missing_aspects": [aspect.value for aspect in validation.missing_aspects],
            "evidence_path": _append_evidence_path(state, "rag"),
        }
    return {
        "sufficient": False,
        "answerability_status": result.status,
        "answerability": result.as_metadata(),
        "source_support": result.source_support,
        "contradictions": result.contradictions,
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
    "_required_aspects_from_state",
    "_validated_answerability",
    "_validation_threshold_for_aspect",
    "_validate_evidence_against_required_aspects",
    "evaluate_sufficiency",
]
