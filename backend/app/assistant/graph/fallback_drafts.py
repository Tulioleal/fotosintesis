from __future__ import annotations

from app.assistant.care_contracts import RequiredAspect
from app.assistant.graph.constants import LEGACY_ASPECT_TRANSLATION
from app.assistant.graph.plant_resolution import _display_name_for_answer
from app.assistant.graph.types import AssistantState, FallbackResponseDraft


def _default_fallback_constraints() -> list[str]:
    return [
        "Output plain text only.",
        "Use the draft answer_language exactly.",
        "Do not use Markdown, HTML, headings, tables, bullets, or numbered lists.",
        "Do not include links unless explicitly supplied as allowed user-facing facts.",
        "Do not mention internal fallback reason codes unless explicitly supplied as allowed user-facing facts.",
        "Do not invent unsupported botanical facts or care recommendations.",
    ]


def _simple_fallback_draft(
    state: AssistantState | dict,
    *,
    intent: str,
    allowed_facts: list[str] | None = None,
    required_points: list[str] | None = None,
    prohibited_points: list[str] | None = None,
) -> FallbackResponseDraft:
    plant_name = _display_name_for_answer(state) or "your plant"
    default_required_points = [
        f"When addressing the plant, use the name provided as 'Plant reference' ({plant_name}). Never replace it with the common name, scientific name, or binomial from the evidence or source metadata.",
    ]
    return FallbackResponseDraft(
        intent=intent,
        answer_language=str(state.get("answer_language") or "es"),
        allowed_facts=allowed_facts or [],
        required_points=required_points if required_points else default_required_points,
        prohibited_points=prohibited_points or [],
        rendering_constraints=_default_fallback_constraints(),
    )


def _missing_taxonomy_draft(state: AssistantState | dict) -> FallbackResponseDraft:
    return _simple_fallback_draft(
        state,
        intent="missing_confirmed_taxonomy",
        allowed_facts=[
            f"Display plant name: {_display_name_for_answer(state) or state.get('plant_hint') or 'not provided'}",
            "Confirmed taxonomy is missing.",
        ],
        required_points=["State that a confirmed scientific name is required before searching reliable care evidence."],
        prohibited_points=[
            "Do not use the nickname or display name as confirmed taxonomy.",
            "Do not provide plant care recommendations.",
        ],
    )


def _conservative_safety_draft(state: AssistantState | dict) -> FallbackResponseDraft:
    plant_name = _display_name_for_answer(state) or "your plant"
    missing_aspects = [LEGACY_ASPECT_TRANSLATION.get(value, value) for value in state.get("missing_aspects", [])]
    if RequiredAspect.toxicity_human_edibility.value in missing_aspects:
        return _simple_fallback_draft(
            state,
            intent="conservative_human_edibility_fallback",
            allowed_facts=[f"Plant reference: {plant_name}", "Direct reliable human-edibility evidence was unavailable."],
            required_points=[
                "State that direct reliable evidence was unavailable.",
                "Recommend not consuming the plant until verified with a reliable toxicological or botanical source.",
                "When addressing the plant, use the name provided as 'Plant reference'. Never replace it with the common name, scientific name, or binomial from the evidence or source metadata.",
            ],
            prohibited_points=[
                "Do not claim the plant is edible.",
                "Do not claim the plant is safe to consume.",
                "Do not give preparation, dosage, or culinary advice.",
            ],
        )
    if RequiredAspect.toxicity_pet_safety.value in missing_aspects:
        return _simple_fallback_draft(
            state,
            intent="conservative_pet_safety_fallback",
            allowed_facts=[f"Plant reference: {plant_name}", "Direct reliable pet/child/skin-safety evidence was unavailable."],
            required_points=[
                "State that direct reliable evidence was unavailable.",
                "Recommend keeping the plant away from pets, children, and skin contact until confirmed.",
                "Recommend veterinary or animal poison-control style help if ingestion occurs and symptoms appear.",
                "For skin contact, recommend washing the area and seeking medical advice if irritation occurs.",
                "When addressing the plant, use the name provided as 'Plant reference'. Never replace it with the common name, scientific name, or binomial from the evidence or source metadata.",
            ],
            prohibited_points=[
                "Do not claim the plant is safe for pets, children, or skin contact.",
                "Do not claim the plant is toxic without direct evidence.",
                "Do not give treatment or dosage advice.",
            ],
        )
    return _simple_fallback_draft(
        state,
        intent="conservative_safety_fallback",
        allowed_facts=[f"Plant reference: {plant_name}", "Direct reliable safety evidence was unavailable."],
        required_points=[
            "State that direct reliable evidence was unavailable.",
            "Recommend consulting a professional for safety guidance.",
            "When addressing the plant, use the name provided as 'Plant reference'. Never replace it with the common name, scientific name, or binomial from the evidence or source metadata.",
        ],
        prohibited_points=["Do not make safety claims without direct evidence."],
    )


def _fallback_response_prompt(draft: FallbackResponseDraft) -> str:
    return (
        "Render a fallback response for a plant-care assistant. Verbalize only this structured draft. "
        "Do not change the fallback intent or policy decision. Output only final plain text.\n"
        f"Intent: {draft.intent}\n"
        f"Answer language: {draft.answer_language}\n"
        f"Allowed user-facing facts: {draft.allowed_facts}\n"
        f"Required points: {draft.required_points}\n"
        f"Prohibited points: {draft.prohibited_points}\n"
        f"Rendering constraints: {draft.rendering_constraints}\n"
        "Final response:"
    )


def _model_generation_failed_draft(
    state: AssistantState | dict,
    *,
    intent: str,
    allowed_facts: list[str],
    limitations: list[str] | None = None,
    source_support: list[dict] | None = None,
    contradictions: list[dict] | None = None,
    missing_aspects: list[str] | None = None,
) -> FallbackResponseDraft:
    draft_limitations = list(limitations or state.get("retrieval", None) and getattr(state.get("retrieval"), "limitations", []) or [])
    draft_source_support = list(source_support or state.get("source_support", []))
    draft_contradictions = list(contradictions or state.get("contradictions", []))
    draft_missing = list(missing_aspects or state.get("missing_aspects", []))
    enriched_facts = list(allowed_facts)
    for support in draft_source_support:
        claim = str(support.get("claim") or "").strip()
        if claim and claim not in enriched_facts:
            enriched_facts.append(claim)
    for contradiction in draft_contradictions:
        detail = str(contradiction.get("detail") or contradiction.get("claim") or "").strip()
        entry = f"Detected contradiction: {detail}"
        if detail and entry not in enriched_facts:
            enriched_facts.append(entry)
    for limitation in draft_limitations[:3]:
        entry = f"Limitation: {limitation}"
        if entry not in enriched_facts:
            enriched_facts.append(entry)
    for missing in draft_missing[:3]:
        entry = f"Missing aspect: {missing}"
        if entry not in enriched_facts:
            enriched_facts.append(entry)
    plant_name = _display_name_for_answer(state) or "your plant"
    return _simple_fallback_draft(
        state,
        intent=intent,
        allowed_facts=enriched_facts,
        required_points=[
            "Provide a brief answer using only the supplied allowed facts.",
            "Mention limitations only if present in the allowed facts.",
            f"When addressing the plant, use the name provided as 'Plant reference' ({plant_name}). Never replace it with the common name, scientific name, or binomial from the evidence or source metadata.",
        ],
        prohibited_points=[
            "Do not add botanical facts beyond the supplied allowed facts.",
            "Do not add links unless the allowed facts explicitly require a user-facing link.",
        ],
    )


def _recovery_draft_for_answer_generation(
    state: AssistantState | dict,
    *,
    intent: str,
    evidence_type: str,
    evidence: str,
    limitations: list[str],
    source_metadata: list[dict],
    missing_aspects: list[str] | None = None,
    extra_context: str = "",
) -> FallbackResponseDraft:
    source_support = list(state.get("source_support", []))
    contradictions = list(state.get("contradictions", []))
    allowed_facts = [evidence] if evidence else []
    for support in source_support:
        claim = str(support.get("claim") or "").strip()
        if claim:
            allowed_facts.append(claim)
    return _model_generation_failed_draft(
        state,
        intent=intent,
        allowed_facts=allowed_facts,
        limitations=limitations,
        source_support=source_support,
        contradictions=contradictions,
        missing_aspects=missing_aspects or state.get("missing_aspects", []),
    )


__all__ = [
    "_conservative_safety_draft",
    "_default_fallback_constraints",
    "_fallback_response_prompt",
    "_missing_taxonomy_draft",
    "_model_generation_failed_draft",
    "_recovery_draft_for_answer_generation",
    "_simple_fallback_draft",
]
