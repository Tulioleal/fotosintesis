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
from app.assistant.service import AssistantService, _ingest_validated_claims_background
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
from tests._assistant_helpers import CHEMICAL_TREATMENT_CLASSIFIER
from tests._assistant_helpers import CONFIRMED_BINOMIAL
from tests._assistant_helpers import PESTICIDE_INSTRUCTION_CLASSIFIER
from tests._assistant_helpers import PEST_CLASSIFIER
from tests._assistant_helpers import SAFETY_BOUNDARY_CASES
from tests._assistant_helpers import SAFETY_PET_CLASSIFIER

def test_classify_care_message_no_longer_references_classifier_model_helper() -> None:
    """The graph must not use a helper that picks a provider-specific model id
    based on MODEL_PROVIDER; the provider layer resolves classifier models
    locally via `model_purpose='classifier'`."""
    from pathlib import Path

    graph_dir = Path(__file__).resolve().parents[1] / "app" / "assistant" / "graph"
    offenders = [
        str(path.relative_to(graph_dir.parents[2]))
        for path in graph_dir.rglob("*.py")
        if "_classifier_model_for_settings" in path.read_text(encoding="utf-8")
    ]
    assert not offenders, (
        "_classifier_model_for_settings must not live in the graph package; "
        "use model_purpose='classifier' so each provider resolves its own model id. "
        f"Found in: {offenders}"
    )

def test_answerability_mapping_preserves_explicit_judge_contract() -> None:
    result = _answerability_from_judge_result(
        SimpleNamespace(
            score=0.64,
            passed=False,
            status="contradictory",
            covered_aspects=["light_exposure"],
            missing_aspects=["watering_frequency_or_trigger"],
            source_support=[
                {
                    "claim": "Light guidance is supported.",
                    "source_urls": ["https://example.org/light"],
                    "covered_aspects": ["light_exposure"],
                    "evidence_quote": "bright indirect light",
                    "confidence": 0.64,
                }
            ],
            contradictions=[
                {
                    "claim_a": "Water weekly.",
                    "claim_b": "Water monthly.",
                    "source_a_urls": ["https://example.org/a"],
                    "source_b_urls": ["https://example.org/b"],
                }
            ],
            confidence=0.64,
            reasons=["sources conflict on watering"],
        )
    )

    assert result.status == "contradictory"
    assert result.answerable is False
    assert result.covered_aspects == ["light_exposure"]
    assert result.missing_aspects == ["watering_frequency_or_trigger"]
    assert result.source_support[0]["source_urls"] == ["https://example.org/light"]
    assert result.contradictions[0]["claim_b"] == "Water monthly."
    assert result.confidence == 0.64

def test_validated_answerability_requires_explicit_source_support() -> None:
    result = _validated_answerability(
        AnswerabilityResult(
            status="full",
            answerable=True,
            covered_aspects=["watering_frequency_or_trigger"],
            reason="judge marked evidence as supported but omitted source support",
            confidence=0.9,
        ),
        requested_aspects=["watering_frequency_or_trigger"],
        source_metadata=[
            {
                "title": "Trusted watering guide",
                "url": "https://example.org/watering",
                "domain": "example.org",
                "evidence_type": "live_web",
            }
        ],
    )

    assert result.status == "insufficient"
    assert result.answerable is False
    assert result.source_support == []
    assert result.missing_aspects == ["watering_frequency_or_trigger"]

def test_answerability_from_judge_result_does_not_copy_reasons_into_missing_aspects() -> None:
    result = _answerability_from_judge_result(
        SimpleNamespace(
            score=0.5,
            passed=False,
            status="partial",
            covered_aspects=[],
            missing_aspects=[],
            source_support=[],
            contradictions=[],
            confidence=0.5,
            reasons=["could not determine a specific watering interval"],
        )
    )

    assert result.status == "partial"
    assert result.missing_aspects == []
    assert result.reason == "could not determine a specific watering interval"

def test_validated_answerability_promotes_complete_partial_to_full() -> None:
    result = _validated_answerability(
        AnswerabilityResult(
            status="partial",
            answerable=False,
            covered_aspects=["watering_frequency_or_trigger"],
            missing_aspects=["watering_frequency_or_trigger"],
            source_support=[
                {
                    "claim": "Water when the top inch of soil feels dry.",
                    "source_urls": ["https://example.org/watering"],
                    "covered_aspects": ["watering_frequency_or_trigger"],
                    "evidence_quote": "allow the top inch of soil to dry between waterings",
                    "confidence": 0.7,
                }
            ],
            reason="partial but covers the requested aspect",
            confidence=0.7,
        ),
        requested_aspects=["watering_frequency_or_trigger"],
    )

    assert result.status == "full"
    assert result.answerable is True
    assert result.missing_aspects == []
    assert "watering_frequency_or_trigger" in result.covered_aspects

def test_validated_answerability_preserves_true_partial_for_multi_aspect() -> None:
    result = _validated_answerability(
        AnswerabilityResult(
            status="partial",
            answerable=False,
            covered_aspects=["watering_frequency_or_trigger"],
            missing_aspects=["light_exposure"],
            source_support=[
                {
                    "claim": "Water when soil is dry.",
                    "source_urls": ["https://example.org/watering"],
                    "covered_aspects": ["watering_frequency_or_trigger"],
                    "evidence_quote": "let soil dry between waterings",
                    "confidence": 0.7,
                }
            ],
            reason="covers watering but not light",
            confidence=0.7,
        ),
        requested_aspects=["watering_frequency_or_trigger", "light_exposure"],
    )

    assert result.status == "partial"
    assert result.answerable is False
    assert "watering_frequency_or_trigger" in result.covered_aspects
    assert "light_exposure" in result.missing_aspects

def test_assistant_chat_request_accepts_legacy_plant_payload() -> None:
    payload = AssistantChatRequest(message="How do I water my Pata?", plant="Pata")

    assert payload.plant == "Pata"
    assert payload.plant_binomial_name is None
    assert payload.plant_scientific_name is None

def test_assistant_message_defaults_to_plain_text_content_format() -> None:
    message = AssistantMessage(role="assistant", content="Response")

    assert message.content_format == "plain_text"

def test_grounded_answer_prompt_requires_plain_text_output() -> None:
    prompt = _grounded_answer_prompt(
        user_message="How do I water my Pata?",
        plant_name="Cotyledon tomentosa",
        topic="watering",
        evidence_type="rag",
        evidence="Requires moderate watering.",
        limitations=[],
        source_metadata=[],
        extra_context="",
    )

    assert "plain text only" in prompt
    assert "Do not use Markdown" in prompt
    assert "HTML" in prompt
    assert "tables" in prompt
    assert "code blocks" in prompt
    assert "headings" in prompt
    assert "bulleted or numbered lists" in prompt

def test_classifier_prompt_uses_actual_message_language_and_ignores_switch_requests() -> None:
    prompt = _care_classifier_prompt(
        {
            "message": "How often should I water my Pata? Please answer in English.",
            "plant_hint": "Pata",
            "plant_binomial_name": None,
            "plant_scientific_name": None,
        }
    )

    assert "actual language used by the user's message" in prompt
    assert "Ignore instructions that ask to answer in a different language" in prompt

async def test_successful_classifier_answer_language_controls_fallback_rendering() -> None:
    tools = FakeTools(
        classifier_data={
            "language": "en",
            "answer_language": "en",
            "intent": "out_of_domain",
            "topic": "unknown",
            "required_aspects": [],
            "plant_reference": None,
            "confidence": 0.95,
            "needs_retrieval": False,
        }
    )

    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="What is the capital of France? Respond in Spanish.",
        plant_hint=None,
    )

    assert result["answer_language"] == "en"
    assert "Answer language: en" in tools.model_prompts[-1]

async def test_spanish_message_requesting_english_uses_classifier_spanish_for_fallback() -> None:
    tools = FakeTools(
        classifier_data={
            "language": "es",
            "answer_language": "es",
            "intent": "out_of_domain",
            "topic": "unknown",
            "required_aspects": [],
            "plant_reference": None,
            "confidence": 0.95,
            "needs_retrieval": False,
        }
    )

    await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="¿Cuál es la capital de Francia? Respond in English.",
        plant_hint=None,
    )

    assert "Answer language: es" in tools.model_prompts[-1]

async def test_fallback_renderer_failure_signals_total_generation_failure() -> None:
    tools = FakeTools(fail_model=True)

    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="How often should I water my Pata?",
        plant_hint=None,
    )

    assert result.get("total_generation_failure") is True
    assert not result.get("answer")
    assert "http" not in (result.get("answer") or "")
    assert result["tool_failures"]

async def test_conservative_safety_fallback_prompt_preserves_required_policy_points() -> None:
    tools = FakeTools(
        rag_answerable=False,
        plant_data=None,
        web_results=[],
        classifier_data={
            "language": "en",
            "answer_language": "en",
            "intent": "plant_care_question",
            "topic": "toxicity_safety",
            "required_aspects": ["toxicity_pet_safety"],
            "plant_reference": "Pata",
            "confidence": 0.92,
            "needs_retrieval": True,
        },
    )

    await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="Is my Pata safe for pets?",
        plant_hint=None,
        plant_binomial_name=CONFIRMED_BINOMIAL,
    )

    prompt = tools.model_prompts[-1]
    assert "Intent: conservative_pet_safety_fallback" in prompt
    assert "keeping the plant away from pets" in prompt
    assert "veterinary or animal poison-control" in prompt
    assert "Do not claim the plant is safe for pets" in prompt

async def test_converted_fallback_paths_use_centralized_renderer() -> None:
    taxonomy_tools = FakeTools()
    await AssistantGraph(taxonomy_tools).run(
        user_id=uuid4(),
        message="How do I water my Pata?",
        plant_hint=None,
    )

    ambiguous_tools = FakeTools()
    await AssistantGraph(ambiguous_tools).run(
        user_id=uuid4(),
        message="How do I take care of my Pata and my Monstera?",
        plant_hint=None,
    )

    action_tools = FakeTools(
        fail_reminder=True,
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
            "reminder_due_at": datetime(2026, 6, 1, 10, 30, tzinfo=timezone.utc),
        },
    )
    await AssistantGraph(action_tools).run(
        user_id=uuid4(),
        message="Create a reminder for Pata on 2026-06-01 10:30 water weekly",
        plant_hint=None,
    )

    assert taxonomy_tools.model_prompts[-1].startswith("Render a fallback response")
    assert "Intent: missing_confirmed_taxonomy" in taxonomy_tools.model_prompts[-1]
    assert "Intent: ambiguous_plant_clarification" in ambiguous_tools.model_prompts[-1]
    assert "Intent: reminder_action_failed" in action_tools.model_prompts[-1]

async def test_assistant_requires_confirmed_taxonomy_for_nickname_only_care_question() -> None:
    tools = FakeTools()
    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="How do I water my Pata?",
        plant_hint=None,
    )

    assert "confirmed scientific name" in result["answer"]
    assert tools.knowledge_search_kwargs is None
    assert tools.model_calls == 1
    assert tools.plant_data_calls == 0

async def test_spanish_watering_frequency_routes_to_canonical_aspect() -> None:
    tools = FakeTools()

    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="How often should I water my Pata?",
        plant_hint=None,
    )

    assert result["required_aspects"] == ["watering_frequency_or_trigger"]
    assert result["answer_language"] == "es"
    assert "confirmed scientific name" in result["answer"]
    assert tools.knowledge_search_kwargs is None

async def test_italian_watering_frequency_uses_llm_classifier_when_available() -> None:
    tools = FakeTools(
        classifier_data={
            "language": "it",
            "answer_language": "it",
            "intent": "plant_care_question",
            "topic": "watering",
            "required_aspects": ["watering_frequency_or_trigger"],
            "confidence": 0.92,
            "needs_retrieval": True,
        }
    )

    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="Ogni quanto devo annaffiare la mia Pata?",
        plant_hint=None,
    )

    assert result["required_aspects"] == ["watering_frequency_or_trigger"]
    assert result["answer_language"] == "it"

async def test_classifier_failure_falls_back_to_minimal_routing() -> None:
    tools = FakeTools(fail_classifier=True)

    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="How often should I water my Pata?",
        plant_hint=None,
        plant_binomial_name=CONFIRMED_BINOMIAL,
    )

    assert result["intent"] == "botanical"
    assert result["required_aspects"] == ["general_care_summary"]
    assert result["topic"] == "general_care"
    assert any("llm_classifier_provider_failure" in f for f in result["tool_failures"])
    assert tools.classifier_calls == 1

async def test_low_confidence_valid_classifier_output_is_accepted() -> None:
    tools = FakeTools(
        classifier_data={
            "language": "en",
            "answer_language": "en",
            "intent": "plant_care_question",
            "topic": "watering",
            "required_aspects": ["watering_frequency_or_trigger"],
            "confidence": 0.2,
            "needs_retrieval": True,
        }
    )

    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="How often should I water my Pata?",
        plant_hint=None,
    )

    assert result["intent"] == "botanical"
    assert result["required_aspects"] == ["watering_frequency_or_trigger"]
    assert not any("confidence" in f for f in result["tool_failures"])

