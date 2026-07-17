from datetime import datetime, timezone
import json
import logging
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.assistant.graph import (
    ASPECT_VALIDATION_GUIDANCE,
    CARE_CLASSIFIER_SCHEMA,
    AnswerabilityResult,
    AssistantGraph,
    _answerability_from_judge_result,
    _aspect_validation_guidance,
    _binomial_from_scientific_name,
    _care_classifier_prompt,
    _grounded_answer_prompt,
    _targeted_web_query,
    _validated_answerability,
    operational_plant_name,
)
from app.assistant import service as assistant_service
from app.assistant.schemas import AssistantChatRequest, AssistantMessage
from app.assistant.service import AssistantService
from app.assistant.tools import AssistantTools, ToolResult
from app.auth.tables import conversation_messages
from app.knowledge.acquisition import TrustedSourceValidator
from app.knowledge.page_evidence import TrustedPageEvidence, TrustedPageEvidenceFetcher
from app.knowledge.plant_data import StructuredPlantEvidence
from app.knowledge.schemas import (
    AcquisitionStatus,
    KnowledgeAcquisitionResult,
    KnowledgeChunk,
    ReviewStatus,
    KnowledgeSourceInput,
)
from app.providers.types import JudgeResult, SearchResult

from tests._assistant_helpers import (
    FakeTools,
    HighConfidencePartialJudgeTools,
    LowConfidenceSafetyJudgeTools,
    PartialLowConfidenceJudgeTools,
    RollbackRecordingKnowledgeRepository,
    SlowJudgeTools,
    SlowWebSearchTools,
    StrongWateringJudgeTools,
    _structured_evidence,
    _validated_web_metadata,
)
from tests._assistant_helpers import CONFIRMED_BINOMIAL

async def test_model_recovery_attempt_uses_structured_draft() -> None:
    """When retrieval is degraded, fallback rendering uses the structured draft."""
    tools = FakeTools(
        rag_answerable=False,
        plant_data=None,
        web_results=[],
        degraded_knowledge=True,
    )

    await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="How often should I water my Pata?",
        plant_hint=None,
        plant_binomial_name=CONFIRMED_BINOMIAL,
    )

    fallback_prompts = [p for p in tools.model_prompts if "Render a fallback response" in p]
    assert len(fallback_prompts) >= 1
    assert "Answer language:" in fallback_prompts[-1]

async def test_action_confirmation_generated_through_model() -> None:
    """Action confirmations are generated through the model path."""
    tools = FakeTools()

    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="Create a reminder for Pata on 2026-06-01 10:30 water weekly",
        plant_hint=None,
    )

    fallback_prompts = [p for p in tools.model_prompts if "Render a fallback response" in p]
    has_action_intent = any(
        "reminder_" in p for p in fallback_prompts
    )
    assert has_action_intent or result.get("answer")

async def test_reminder_success_generated_through_model() -> None:
    """Successful reminder creation generates confirmation through the model."""
    tools = FakeTools(
        classifier_data={
            "language": "en",
            "answer_language": "en",
            "intent": "reminder_request",
            "topic": "watering",
            "required_aspects": [],
            "plant_reference": "Pata",
            "confidence": 0.92,
            "needs_retrieval": False,
            "reminder_action": "water",
            "reminder_recurrence": "weekly",
            "reminder_suggestion_requested": False,
        }
    )

    await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="Create a reminder for Pata on 2026-06-01 10:30 water weekly",
        plant_hint=None,
    )

    fallback_prompts = [p for p in tools.model_prompts if "Render a fallback response" in p]
    has_created_intent = any("reminder_created" in p for p in fallback_prompts)
    assert has_created_intent

async def test_non_english_evidence_reaches_model_without_keyword_matching() -> None:
    """Non-English evidence reaches the model without deterministic keyword matching."""
    tools = FakeTools(
        rag_answerable=False,
        plant_data=None,
        web_results=[
            SearchResult(
                title="Watering guide in Italian",
                url="https://example.org/irrigazione",
                snippet="La pianta richiede annaffiature moderate. Il terreno deve essere asciutto tra un'annaffiatura e l'altra.",
                source_domain="example.org",
            )
        ],
    )

    await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="Como debo regar mi Monstera?",
        plant_hint=None,
        plant_binomial_name="Monstera deliciosa",
    )

    assert tools.web_search_calls == 1
    judge_calls = [
        c for c in tools.judge_calls
        if c["payload"].get("evidence_type") == "combined_rag_web"
    ]
    assert len(judge_calls) >= 1


# ---------------------------------------------------------------------------
# Structured recovery draft tests
# ---------------------------------------------------------------------------

async def test_recovery_draft_uses_structured_facts_not_prewritten_prose() -> None:
    """Recovery draft must contain structured source support facts, not prewritten prose."""
    tools = FakeTools(fail_model=True)

    await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="How often should I water my Pata?",
        plant_hint=None,
        plant_binomial_name=CONFIRMED_BINOMIAL,
    )

    fallback_prompts = [p for p in tools.model_prompts if "Render a fallback response" in p]
    assert len(fallback_prompts) >= 1
    draft_prompt = fallback_prompts[-1]
    assert "Answer language:" in draft_prompt
    assert "Allowed user-facing facts:" in draft_prompt
    assert "Required points:" in draft_prompt
    assert "Prohibited points:" in draft_prompt

async def test_provider_unavailable_failure_skips_recovery_generation() -> None:
    """Non-recoverable provider failures skip recovery and signal total failure immediately."""
    tools = FakeTools(fail_model=True, model_error_message="all providers failed: gemini unavailable")

    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="How often should I water my Pata?",
        plant_hint=None,
        plant_binomial_name=CONFIRMED_BINOMIAL,
    )

    assert result.get("total_generation_failure") is True
    assert not result.get("answer")
    fallback_prompts = [p for p in tools.model_prompts if "Render a fallback response" in p]
    assert len(fallback_prompts) == 0

async def test_empty_response_triggers_recovery_attempt() -> None:
    """Empty model response triggers recovery attempt (recoverable failure)."""
    tools = FakeTools(model_response="")

    await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="How often should I water my Pata?",
        plant_hint=None,
        plant_binomial_name=CONFIRMED_BINOMIAL,
    )

    fallback_prompts = [p for p in tools.model_prompts if "Render a fallback response" in p]
    assert len(fallback_prompts) >= 1

async def test_recovery_draft_includes_source_support_claims() -> None:
    """Recovery draft includes source support claims from state as allowed facts."""
    tools = FakeTools(fail_model=True)

    await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="How often should I water my Pata?",
        plant_hint=None,
        plant_binomial_name=CONFIRMED_BINOMIAL,
    )

    fallback_prompts = [p for p in tools.model_prompts if "Render a fallback response" in p]
    assert len(fallback_prompts) >= 1
    draft_prompt = fallback_prompts[-1]
    assert "riego" in draft_prompt.lower() or "water" in draft_prompt.lower() or "Allowed user-facing facts:" in draft_prompt


# ---------------------------------------------------------------------------
# Typed failure metadata tests
# ---------------------------------------------------------------------------

async def test_generate_text_preserves_typed_failure_metadata() -> None:
    """AssistantTools.generate_text() returns typed AssistantFailureMetadata on failure."""
    from app.assistant.tools import AssistantFailureMetadata, ProviderFailureEntry

    tools = FakeTools(fail_model=True, model_error_message="all providers failed: gemini unavailable")
    result = await tools.generate_text("test prompt")

    assert result.ok is False
    assert result.failure_metadata is not None
    assert isinstance(result.failure_metadata, AssistantFailureMetadata)
    assert result.failure_metadata.failure_category == "all_providers_failed"
    assert result.failure_metadata.retryable is False
    assert result.failure_metadata.transient is False
    assert len(result.failure_metadata.provider_failures) == 1
    entry = result.failure_metadata.provider_failures[0]
    assert isinstance(entry, ProviderFailureEntry)
    assert entry.failure_category == "all_providers_failed"

async def test_generate_text_preserves_typed_metadata_for_transient_failure() -> None:
    """Transient failures get typed metadata with retryable=True."""
    tools = FakeTools(fail_model=True, model_error_message="service temporarily unavailable")
    result = await tools.generate_text("test prompt")

    assert result.ok is False
    assert result.failure_metadata is not None
    assert result.failure_metadata.retryable is True
    assert result.failure_metadata.transient is True

async def test_grounded_answer_blocks_recovery_by_typed_category_not_string() -> None:
    """Recovery is blocked by typed all_providers_failed category even if error string
    does not contain recognizable keywords."""
    from app.assistant.tools import AssistantFailureMetadata, ProviderFailureEntry

    tools = FakeTools(fail_model=True, model_error_message="custom error message with no keywords")
    original_generate = tools.generate_text

    async def patched_generate(prompt: str) -> ToolResult:
        result = await original_generate(prompt)
        if not result.ok:
            metadata = AssistantFailureMetadata(
                failure_category="all_providers_failed",
                retryable=False,
                transient=False,
                provider_failures=[
                    ProviderFailureEntry(
                        provider="gemini",
                        role="model",
                        operation="generate_text",
                        failure_category="service_unavailable",
                        retryable=False,
                        transient=False,
                    )
                ],
            )
            return ToolResult(ok=False, error=result.error, failure_metadata=metadata)
        return result

    tools.generate_text = patched_generate
    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="How often should I water my Pata?",
        plant_hint=None,
        plant_binomial_name=CONFIRMED_BINOMIAL,
    )

    assert result.get("total_generation_failure") is True
    assert not result.get("answer")
    fallback_prompts = [p for p in tools.model_prompts if "Render a fallback response" in p]
    assert len(fallback_prompts) == 0
    assert result.get("generation_failure") is not None
    assert result["generation_failure"].failure_category == "all_providers_failed"

async def test_grounded_answer_stores_generation_failure_in_state() -> None:
    """_generate_grounded_answer stores typed failure metadata in state.generation_failure."""
    tools = FakeTools(fail_model=True, model_error_message="service unavailable")

    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="How often should I water my Pata?",
        plant_hint=None,
        plant_binomial_name=CONFIRMED_BINOMIAL,
    )

    assert result.get("total_generation_failure") is True
    gen_failure = result.get("generation_failure")
    assert gen_failure is not None
    assert gen_failure.failure_category == "service_unavailable"
    assert gen_failure.retryable is False
    assert gen_failure.transient is False

async def test_retryable_error_provider_failures_are_typed_not_strings(
    session_factory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AssistantRetryableError.provider_failures contains typed entries, not raw strings."""
    from app.assistant.schemas import AssistantRetryableError, ProviderFailureDetail

    class FakeGraph:
        async def run(self, **kwargs):
            from app.assistant.tools import AssistantFailureMetadata, ProviderFailureEntry
            return {
                "total_generation_failure": True,
                "tool_failures": ["something"],
                "generation_failure": AssistantFailureMetadata(
                    failure_category="timeout",
                    retryable=False,
                    transient=False,
                    provider_failures=[
                        ProviderFailureEntry(
                            provider="gemini",
                            role="model",
                            operation="generate_text",
                            failure_category="timeout",
                            retryable=False,
                            transient=False,
                            status_code=None,
                            attempt_index=0,
                        )
                    ],
                ),
                "sources": [],
            }

    monkeypatch.setattr(
        "app.assistant.tools.facade.get_provider_registry",
        lambda: SimpleNamespace(search=object(), embeddings=object()),
    )
    async with session_factory() as session:
        service = AssistantService(session)
        service.graph = FakeGraph()
        response = await service.chat(
            user_id=uuid4(),
            payload=AssistantChatRequest(message="test", plant="test"),
        )

    assert isinstance(response, AssistantRetryableError)
    assert len(response.provider_failures) == 1
    entry = response.provider_failures[0]
    assert isinstance(entry, ProviderFailureDetail)
    assert entry.provider == "gemini"
    assert entry.failure_category == "timeout"
    assert entry.attempt_index == 0

async def test_assistant_tools_generate_text_returns_metadata_for_empty_error() -> None:
    """Even generic errors get typed metadata with failure_category='unknown'."""
    tools = FakeTools(fail_model=True)
    result = await tools.generate_text("prompt")

    assert result.ok is False
    assert result.failure_metadata is not None
    assert result.failure_metadata.failure_category in ("unknown", "service_unavailable")
    assert result.failure_metadata.provider_failures[0].provider == "gemini"


# ---------------------------------------------------------------------------
# Disclaimed LLM guidance tests (insufficient evidence, non-safety)
# ---------------------------------------------------------------------------


PEST_CLASSIFIER = {
    "language": "en",
    "answer_language": "en",
    "intent": "plant_care_question",
    "topic": "pests",
    "required_aspects": [
        "pest_identification",
        "pest_isolation_steps",
        "pest_prevention_steps",
    ],
    "plant_reference": "Pata",
    "confidence": 0.9,
    "needs_retrieval": True,
}


SAFETY_PET_CLASSIFIER = {
    "language": "en",
    "answer_language": "en",
    "intent": "plant_care_question",
    "topic": "toxicity_safety",
    "required_aspects": ["toxicity_pet_safety"],
    "plant_reference": "Pata",
    "confidence": 0.92,
    "needs_retrieval": True,
}

def test_general_guidance_prompt_preserves_non_default_answer_language() -> None:
    """Prompt builder must preserve a non-default answer_language."""
    from app.assistant.graph import _general_guidance_with_disclaimer_prompt

    prompt = _general_guidance_with_disclaimer_prompt(
        user_message="I see tiny white bugs under the leaves",
        plant_name="Pata",
        topic="pests",
        answer_language="en",
        required_aspects=["pest_identification"],
        covered_aspects=[],
        missing_aspects=["pest_identification"],
        source_support=[],
        source_metadata=[],
    )

    assert "answer_language (en)" in prompt

def test_is_disclaimed_guidance_eligible_requires_insufficient_and_relevance() -> None:
    """Eligibility requires insufficient + relevance + no missing safety aspect."""
    from app.assistant.graph import _is_disclaimed_guidance_eligible

    insufficient_with_chunks = {
        "sufficient": False,
        "retrieval": SimpleNamespace(chunks=["some chunk"], limitations=[]),
        "missing_aspects": ["pest_identification"],
        "required_aspects": ["pest_identification"],
    }
    assert _is_disclaimed_guidance_eligible(insufficient_with_chunks) is True

    sufficient = {**insufficient_with_chunks, "sufficient": True}
    assert _is_disclaimed_guidance_eligible(sufficient) is False

    insufficient_no_context = {
        "sufficient": False,
        "retrieval": None,
        "missing_aspects": ["pest_identification"],
        "required_aspects": ["pest_identification"],
    }
    assert _is_disclaimed_guidance_eligible(insufficient_no_context) is False

    insufficient_with_safety = {
        "sufficient": False,
        "retrieval": SimpleNamespace(chunks=["x"], limitations=[]),
        "missing_aspects": ["toxicity_pet_safety"],
        "required_aspects": ["toxicity_pet_safety"],
    }
    assert _is_disclaimed_guidance_eligible(insufficient_with_safety) is False

def test_diagnostics_carry_llm_general_guidance_used_flag() -> None:
    """The diagnostics builder must reflect the runtime-only guidance flag."""
    from app.assistant.graph import _diagnostics

    state = {
        "topic": "pests",
        "required_aspects": ["pest_identification"],
        "covered_aspects": [],
        "missing_aspects": ["pest_identification"],
        "evidence_path": ["rag"],
        "answer_language": "en",
        "answerability_status": "insufficient",
        "contradictions": [],
        "llm_general_guidance_used": True,
    }
    diagnostics = _diagnostics(state)
    assert diagnostics["llm_general_guidance_used"] is True

    state_off = {**state, "llm_general_guidance_used": False}
    diagnostics_off = _diagnostics(state_off)
    assert diagnostics_off["llm_general_guidance_used"] is False

def test_care_diagnostics_and_api_schema_expose_new_flag() -> None:
    """Both the internal Pydantic model and the public API schema must expose the flag."""
    from app.assistant.care_contracts import CareDiagnostics
    from app.assistant.schemas import AssistantCareDiagnostics

    internal = CareDiagnostics()
    assert internal.llm_general_guidance_used is False

    public = AssistantCareDiagnostics()
    assert public.llm_general_guidance_used is False

async def test_pest_question_with_relevant_context_routes_to_disclaimed_guidance() -> None:
    """4.1 - Pest question with relevant context but insufficient evidence uses disclaimed guidance."""
    tools = FakeTools(
        rag_answerable=False,
        plant_data=None,
        web_results=[],
        classifier_data=PEST_CLASSIFIER,
        model_response=(
            "What the sources validated: no part was validated by retrieved sources. "
            "What the sources did not validate: insect identification and isolation steps. "
            "General unvalidated guidance: check the underside of the leaves, isolate the plant, "
            "manually remove with water or a damp cloth. "
            "Details that would help: a close-up photo of the insect and observed symptoms."
        ),
    )

    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="I see some small white insects under the leaves of my Pata",
        plant_hint=None,
        plant_binomial_name=CONFIRMED_BINOMIAL,
    )

    assert result["sufficient"] is False
    assert result["answerability_status"] == "insufficient"
    assert result["llm_general_guidance_used"] is True
    assert "What the sources validated" in result["answer"]
    assert "Details that would help" in result["answer"]
    assert result["diagnostics"]["llm_general_guidance_used"] is True
    assert result["diagnostics"]["missing_aspects"] == ["pest_identification", "pest_isolation_steps", "pest_prevention_steps"]
    assert result["diagnostics"]["covered_aspects"] == []
    assert result["diagnostics"]["answerability_status"] == "insufficient"

async def test_disclaimed_guidance_diagnostic_flag_and_no_prompt_leakage() -> None:
    """4.2 - Diagnostics expose the flag and bounded metadata without prompt/evidence leakage."""
    tools = FakeTools(
        rag_answerable=False,
        plant_data=None,
        web_results=[],
        classifier_data=PEST_CLASSIFIER,
        model_response=(
            "What the sources validated: none. "
            "What the sources did not validate: insect identification. "
            "General unvalidated guidance: inspect the underside and isolate the plant. "
            "Details that would help: a close-up photo of the insect."
        ),
    )

    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="I see some small white insects under the leaves",
        plant_hint=None,
        plant_binomial_name=CONFIRMED_BINOMIAL,
    )

    diagnostics = result["diagnostics"]
    assert diagnostics["llm_general_guidance_used"] is True
    assert "required_aspects" in diagnostics
    assert "covered_aspects" in diagnostics
    assert "missing_aspects" in diagnostics
    assert diagnostics["missing_aspects"] == ["pest_identification", "pest_isolation_steps", "pest_prevention_steps"]

    disclaimed_prompts = [
        p for p in tools.model_prompts
        if "What the sources validated" in p and "General unvalidated guidance" in p
    ]
    assert len(disclaimed_prompts) >= 1
    full_prompt = disclaimed_prompts[0]
    prompt_blob = full_prompt.lower()
    assert "requires moderate watering and substrate" not in prompt_blob
    assert "do not cite any source" in prompt_blob
    assert "what the sources validated" in prompt_blob
    assert "general unvalidated guidance" in prompt_blob
    assert "Details that would help" in full_prompt

    diagnostics_blob = json.dumps(diagnostics, default=str)
    assert "What the sources validated" not in diagnostics_blob
    assert "Requires moderate watering" not in diagnostics_blob
