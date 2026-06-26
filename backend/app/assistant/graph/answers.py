from __future__ import annotations

from app.assistant.care_contracts import CareClassification, CareDiagnostics, RequiredAspect
from app.assistant.graph.constants import LEGACY_ASPECT_TRANSLATION
from app.assistant.graph.helpers import logger
from app.assistant.graph.plant_resolution import _display_name_for_answer, _operational_name_for_tools, _taxonomy_context
from app.assistant.graph.prompts import (
    _general_guidance_with_disclaimer_prompt,
    _grounded_answer_prompt,
)
from app.assistant.graph.routes import _is_disclaimed_guidance_eligible
from app.assistant.graph.safety import _has_missing_safety_aspect
from app.assistant.graph.types import AssistantState
from app.assistant.graph_shared import _shorten, _strip_source_attribution_from_answer
from app.assistant.tools import AssistantFailureMetadata
from app.knowledge.page_evidence import TrustedPageEvidence
from app.knowledge.plant_data import StructuredPlantEvidence
from app.observability.tracing import get_trace_id
from app.providers.fallback import NON_RECOVERABLE_FAILURE_CATEGORIES

# Re-exports from the split submodules so existing `from app.assistant.graph.answers import ...`
# call sites (used by tests, `web_evidence.py`, `answerability.py`, and the package `__init__`)
# continue to resolve. The actual implementations live in `fallback_drafts.py` and `nodes.py`.
from app.assistant.graph.fallback_drafts import (
    _conservative_safety_draft,
    _default_fallback_constraints,
    _fallback_response_prompt,
    _missing_taxonomy_draft,
    _model_generation_failed_draft,
    _recovery_draft_for_answer_generation,
    _simple_fallback_draft,
)
from app.assistant.graph.nodes import (
    _append_reason,
    _handle_reminder,
    clarify,
    failure,
    handle_action,
    load_user_context,
    retrieve,
)


def _diagnostics(state: AssistantState | dict) -> dict[str, object]:
    classification = state.get("care_classification")
    intent = classification.intent.value if isinstance(classification, CareClassification) else None
    diagnostics = CareDiagnostics(
        intent=intent,
        topic=state.get("topic"),
        required_aspects=list(state.get("required_aspects", [])),
        covered_aspects=list(state.get("covered_aspects", [])),
        missing_aspects=list(state.get("missing_aspects", [])),
        evidence_path=list(state.get("evidence_path", [])),
        answer_language=state.get("answer_language"),
        llm_general_guidance_used=bool(state.get("llm_general_guidance_used", False)),
    ).model_dump(mode="json")
    diagnostics["answerability_status"] = state.get("answerability_status")
    diagnostics["contradictions"] = list(state.get("contradictions", []))
    provider_fallbacks = state.get("provider_fallbacks", [])
    if provider_fallbacks:
        diagnostics["provider_fallbacks"] = list(provider_fallbacks)
    return diagnostics


def _log_answerability_decision(evidence_type: str, result, fallback_reason: str | None) -> None:
    logger.info(
        "assistant answerability decision",
        extra={
            "ctx_trace_id": get_trace_id(),
            "ctx_evidence_type": evidence_type,
            "ctx_status": result.status,
            "ctx_answerable": result.answerable,
            "ctx_covered_aspects": result.covered_aspects,
            "ctx_missing_aspects": result.missing_aspects,
            "ctx_answerability_confidence": result.confidence,
            "ctx_source_support_count": len(result.source_support),
            "ctx_contradictions_count": len(result.contradictions),
            "ctx_fallback_reason": fallback_reason,
        },
    )


def _log_fallback_route(reason: str, *, evidence_type: str) -> None:
    logger.info(
        "assistant fallback route",
        extra={
            "ctx_trace_id": get_trace_id(),
            "ctx_evidence_type": evidence_type,
            "ctx_fallback_reason": reason,
        },
    )


def _conservative_safety_answer(state: AssistantState) -> str | None:
    plant_name = _display_name_for_answer(state) or "your plant"
    missing_aspects = [LEGACY_ASPECT_TRANSLATION.get(value, value) for value in state.get("missing_aspects", [])]
    if RequiredAspect.toxicity_human_edibility.value in missing_aspects:
        return f"I did not find direct and reliable evidence on whether {plant_name} is edible. For safety, do not consume it or use it in preparations until verified with a reliable toxicological or botanical source."
    if RequiredAspect.toxicity_pet_safety.value in missing_aspects:
        return f"I did not find direct and reliable evidence on the safety of {plant_name} for pets, children, or skin contact. As a precaution, keep it out of reach of pets and children until confirmed with a reliable veterinary or toxicological source. If ingestion or skin contact occurs and symptoms appear, consult a veterinarian or poison control center."
    return None


def is_recoverable_generation_failure(failure_metadata: AssistantFailureMetadata) -> bool:
    if failure_metadata.failure_category in NON_RECOVERABLE_FAILURE_CATEGORIES:
        return False
    return all(entry.failure_category not in NON_RECOVERABLE_FAILURE_CATEGORIES for entry in failure_metadata.provider_failures)


async def generate_answer(owner, state: AssistantState) -> dict:
    if state.get("answer"):
        return {}
    retrieval = state.get("retrieval")
    chunks = getattr(retrieval, "chunks", []) if retrieval else []
    limitations = list(getattr(retrieval, "limitations", []) if retrieval else [])
    if not state.get("sufficient"):
        web_results = state.get("web_results", [])
        if web_results:
            if _has_missing_safety_aspect(state) and _conservative_safety_answer(state):
                rendered = await owner._generate_fallback_response(state, _conservative_safety_draft(state))
                return {**rendered, "fallback_reasons": _append_reason(state, "conservative_safety_fallback")}
            return await owner._generate_web_answer(state, web_results)
        if _has_missing_safety_aspect(state):
            rendered = await owner._generate_fallback_response(state, _conservative_safety_draft(state))
            return {**rendered, "fallback_reasons": _append_reason(state, "conservative_safety_fallback")}
        if state.get("covered_aspects") and chunks:
            return await owner._generate_grounded_answer(
                state,
                plant_name=_display_name_for_answer(state),
                evidence_type="rag",
                evidence=" ".join(_shorten(chunk.content, 280) for chunk in chunks[:3]),
                limitations=[f"Could not validate: {', '.join(state.get('missing_aspects', []))}"],
                source_metadata=state.get("sources", []),
            )
        if _is_disclaimed_guidance_eligible(state):
            return await owner._generate_disclaimed_guidance(state)
        return await owner.clarify(state)
    if not chunks:
        return await owner.clarify(state)
    return await owner._generate_grounded_answer(
        state,
        plant_name=_display_name_for_answer(state),
        evidence_type="rag",
        evidence=" ".join(_shorten(chunk.content, 280) for chunk in chunks[:3]),
        limitations=limitations,
        source_metadata=state.get("sources", []),
    )


async def _generate_structured_answer(owner, state: AssistantState, evidence: StructuredPlantEvidence) -> dict:
    plant_name = _display_name_for_answer(state) or evidence.scientific_name
    providers = ", ".join(evidence.providers)
    source_metadata = state.get("sources", []) + [{"providers": evidence.providers}]
    return await owner._generate_grounded_answer(
        state,
        plant_name=plant_name,
        evidence_type="structured_api",
        evidence=_shorten(evidence.content, 1200),
        limitations=list(evidence.missing_fields),
        source_metadata=source_metadata,
        extra_context=f"Providers: {providers}.",
    )


async def _generate_web_answer(owner, state: AssistantState, web_results: list[TrustedPageEvidence]) -> dict:
    from app.assistant.graph.web_evidence import _combined_answer_evidence, _supported_rag_evidence, _validated_claim_payloads

    plant_name = _display_name_for_answer(state)
    topic = state.get("topic") or "care"
    synthesized = await owner._generate_grounded_answer(
        state,
        plant_name=plant_name,
        evidence_type="combined_rag_web" if _supported_rag_evidence(state) else "live_web",
        evidence=_combined_answer_evidence(state, web_results),
        limitations=["This guide uses recent web sources that have not yet been incorporated into the persisted knowledge."],
        source_metadata=state.get("sources", []),
    )
    return {
        **synthesized,
        "ingestion_claims": _validated_claim_payloads(
            state,
            scientific_name=str(_operational_name_for_tools(state) or plant_name or ""),
            topic=topic,
        ),
    }


async def _generate_disclaimed_guidance(owner, state: AssistantState) -> dict:
    prompt = _general_guidance_with_disclaimer_prompt(
        user_message=state["message"],
        plant_name=_display_name_for_answer(state),
        topic=state.get("topic") or "care",
        answer_language=state.get("answer_language") or "es",
        required_aspects=state.get("required_aspects", []),
        covered_aspects=state.get("covered_aspects", []),
        missing_aspects=state.get("missing_aspects", []),
        source_support=state.get("source_support", []),
        source_metadata=state.get("sources", []),
        extra_context=_taxonomy_context(state),
    )
    marked_state = {**state, "llm_general_guidance_used": True}
    result = await owner.tools.generate_text(prompt)
    if not result.ok:
        failure = result.error or "model_generate_text failed"
        metadata = result.failure_metadata
        if metadata and not is_recoverable_generation_failure(metadata):
            return {"answer": None, "total_generation_failure": True, "tool_failures": state.get("tool_failures", []) + [failure], "generation_failure": metadata, "diagnostics": _diagnostics(marked_state), "llm_general_guidance_used": True}
        rendered = await owner._generate_fallback_response({**marked_state, "tool_failures": state.get("tool_failures", []) + [failure]}, _recovery_draft_for_answer_generation(state, intent="model_generation_failed", evidence_type="disclaimed_guidance", evidence="", limitations=[], source_metadata=[]))
        rendered["llm_general_guidance_used"] = True
        return rendered
    answer = str(result.data or "").strip()
    if not answer:
        rendered = await owner._generate_fallback_response({**marked_state, "tool_failures": state.get("tool_failures", []) + ["model_generate_text failed: empty response"]}, _recovery_draft_for_answer_generation(state, intent="model_generation_failed", evidence_type="disclaimed_guidance", evidence="", limitations=[], source_metadata=[]))
        rendered["llm_general_guidance_used"] = True
        return rendered
    return {"answer": answer, "diagnostics": _diagnostics(marked_state), "llm_general_guidance_used": True}


async def _generate_grounded_answer(
    owner,
    state: AssistantState,
    *,
    plant_name: str | None,
    evidence_type: str,
    evidence: str,
    limitations: list[str],
    source_metadata: list[dict],
    extra_context: str = "",
) -> dict:
    prompt = _grounded_answer_prompt(
        user_message=state["message"],
        plant_name=plant_name,
        topic=state.get("topic") or "care",
        evidence_type=evidence_type,
        evidence=evidence,
        limitations=limitations,
        source_metadata=source_metadata,
        extra_context=_taxonomy_context(state, extra_context),
        answer_language=state.get("answer_language") or "es",
        required_aspects=state.get("required_aspects", []),
        covered_aspects=state.get("covered_aspects", []),
        missing_aspects=state.get("missing_aspects", []),
        answerability_status=state.get("answerability_status") or ("full" if state.get("sufficient") else "insufficient"),
        source_support=state.get("source_support", []),
        contradictions=state.get("contradictions", []),
    )
    result = await owner.tools.generate_text(prompt)
    if not result.ok:
        failure = result.error or "model_generate_text failed"
        metadata = result.failure_metadata
        if metadata and not is_recoverable_generation_failure(metadata):
            return {"answer": None, "total_generation_failure": True, "tool_failures": state.get("tool_failures", []) + [failure], "generation_failure": metadata, "diagnostics": _diagnostics(state)}
        rendered = await owner._generate_fallback_response({**state, "tool_failures": state.get("tool_failures", []) + [failure]}, _recovery_draft_for_answer_generation(state, intent="model_generation_failed", evidence_type=evidence_type, evidence=evidence, limitations=limitations, source_metadata=source_metadata))
        return {**rendered, "tool_failures": rendered.get("tool_failures", state.get("tool_failures", []) + [failure])}
    answer = _strip_source_attribution_from_answer(str(result.data or "").strip())
    if not answer:
        rendered = await owner._generate_fallback_response({**state, "tool_failures": state.get("tool_failures", []) + ["model_generate_text failed: empty response"]}, _recovery_draft_for_answer_generation(state, intent="model_generation_failed", evidence_type=evidence_type, evidence=evidence, limitations=limitations, source_metadata=source_metadata))
        return {**rendered, "tool_failures": rendered.get("tool_failures", state.get("tool_failures", []) + ["model_generate_text failed: empty response"])}
    return {"answer": answer, "diagnostics": _diagnostics(state)}


async def _generate_fallback_response(owner, state: AssistantState | dict, draft) -> dict:
    result = await owner.tools.generate_text(_fallback_response_prompt(draft))
    if not result.ok:
        return {"answer": None, "total_generation_failure": True, "tool_failures": state.get("tool_failures", []) + [result.error or "fallback_generate_text failed"], "generation_failure": result.failure_metadata, "diagnostics": _diagnostics(state)}
    answer = str(result.data or "").strip()
    if not answer:
        return {"answer": None, "total_generation_failure": True, "tool_failures": state.get("tool_failures", []) + ["fallback_generate_text failed: empty response"], "generation_failure": AssistantFailureMetadata(failure_category="empty_response", retryable=True, transient=True), "diagnostics": _diagnostics(state)}
    return {"answer": answer, "diagnostics": _diagnostics(state)}


__all__ = [
    "_append_reason",
    "_conservative_safety_answer",
    "_conservative_safety_draft",
    "_default_fallback_constraints",
    "_diagnostics",
    "_fallback_response_prompt",
    "_generate_disclaimed_guidance",
    "_generate_fallback_response",
    "_generate_grounded_answer",
    "_generate_structured_answer",
    "_generate_web_answer",
    "_handle_reminder",
    "_log_answerability_decision",
    "_log_fallback_route",
    "_missing_taxonomy_draft",
    "_model_generation_failed_draft",
    "_recovery_draft_for_answer_generation",
    "_simple_fallback_draft",
    "clarify",
    "failure",
    "generate_answer",
    "handle_action",
    "is_recoverable_generation_failure",
    "load_user_context",
    "retrieve",
]
