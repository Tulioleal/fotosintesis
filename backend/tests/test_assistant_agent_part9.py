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

async def test_classifier_diagnosis_returns_diagnosis_topic() -> None:
    tools = FakeTools(
        classifier_data={
            "language": "en",
            "answer_language": "en",
            "intent": "plant_care_question",
            "topic": "diagnosis",
            "required_aspects": ["diagnosis_leaf_color_change_causes"],
            "plant_reference": "Pata",
            "confidence": 0.92,
            "needs_retrieval": True,
        }
    )
    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="Why are my leaves yellow?",
        plant_hint=None,
    )
    assert result["topic"] == "diagnosis"
    assert "diagnosis_leaf_color_change_causes" in result["required_aspects"]

async def test_classifier_pests_returns_pest_aspects() -> None:
    tools = FakeTools(
        classifier_data={
            "language": "en",
            "answer_language": "en",
            "intent": "plant_care_question",
            "topic": "pests",
            "required_aspects": ["pest_treatment_action"],
            "plant_reference": "Pata",
            "confidence": 0.92,
            "needs_retrieval": True,
        }
    )
    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="How do I treat pests on my Pata?",
        plant_hint=None,
    )
    assert result["topic"] == "pests"
    assert "pest_treatment_action" in result["required_aspects"]
    assert "treatment_action" not in result["required_aspects"]

async def test_classifier_disease_returns_disease_aspects() -> None:
    tools = FakeTools(
        classifier_data={
            "language": "en",
            "answer_language": "en",
            "intent": "plant_care_question",
            "topic": "disease",
            "required_aspects": ["disease_prevention_steps"],
            "plant_reference": "Pata",
            "confidence": 0.92,
            "needs_retrieval": True,
        }
    )
    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="How do I prevent diseases in my Pata?",
        plant_hint=None,
    )
    assert result["topic"] == "disease"
    assert "disease_prevention_steps" in result["required_aspects"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("message", "topic", "required_aspects"),
    [
        (
            "What fertilizer does my Pata need?",
            "nutrition",
            ["nutrition_feeding_schedule", "nutrition_fertilizer_type"],
        ),
        ("When should I prune my Pata?", "pruning", ["pruning_timing"]),
        (
            "How do I propagate cuttings of my Pata?",
            "propagation",
            ["propagation_rooting_conditions"],
        ),
        (
            "What temperature can my Pata tolerate?",
            "climate",
            ["climate_temperature_range"],
        ),
        ("What humidity does my Pata need?", "humidity", ["humidity_preference"]),
        (
            "What is the native range of my Pata?",
            "taxonomy",
            ["taxonomy_native_range"],
        ),
        (
            "Does my Pata help pollinators?",
            "ecology",
            ["ecology_pollinator_support"],
        ),
    ],
)

async def test_classifier_returns_expanded_domain_aspects(
    message: str,
    topic: str,
    required_aspects: list[str],
) -> None:
    tools = FakeTools(
        classifier_data={
            "language": "en",
            "answer_language": "en",
            "intent": "plant_care_question",
            "topic": topic,
            "required_aspects": required_aspects,
            "plant_reference": "Pata",
            "confidence": 0.92,
            "needs_retrieval": True,
        }
    )
    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message=message,
        plant_hint=None,
    )
    assert result["topic"] == topic
    for aspect in required_aspects:
        assert aspect in result["required_aspects"]

async def test_classifier_repotting_returns_repotting_aspects() -> None:
    tools = FakeTools(
        classifier_data={
            "language": "en",
            "answer_language": "en",
            "intent": "plant_care_question",
            "topic": "repotting",
            "required_aspects": ["repotting_timing", "repotting_post_care"],
            "plant_reference": "Pata",
            "confidence": 0.92,
            "needs_retrieval": True,
        }
    )
    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="When should I repot my Pata?",
        plant_hint=None,
    )
    assert result["topic"] == "repotting"
    assert "repotting_timing" in result["required_aspects"]
    assert "repotting_post_care" in result["required_aspects"]

async def test_symptom_question_prefers_diagnosis_aspects() -> None:
    tools = FakeTools(
        classifier_data={
            "language": "en",
            "answer_language": "en",
            "intent": "plant_care_question",
            "topic": "diagnosis",
            "required_aspects": ["diagnosis_leaf_color_change_causes"],
            "plant_reference": "Pata",
            "confidence": 0.92,
            "needs_retrieval": True,
        }
    )
    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="Why are my Pata's leaves yellow?",
        plant_hint=None,
    )
    assert result["topic"] == "diagnosis"
    assert "diagnosis_leaf_color_change_causes" in result["required_aspects"]
    assert "watering_frequency_or_trigger" not in result["required_aspects"]
    assert "pest_identification" not in result["required_aspects"]

async def test_answerability_rejects_full_when_safety_aspect_missing() -> None:
    result = _validated_answerability(
        AnswerabilityResult(
            status="full",
            answerable=True,
            covered_aspects=["watering_frequency_or_trigger"],
            source_support=[
                {
                    "claim": "Water when soil is dry.",
                    "source_urls": ["https://example.org/watering"],
                    "covered_aspects": ["watering_frequency_or_trigger"],
                    "evidence_quote": "water when the top inch of soil feels dry",
                    "confidence": 0.8,
                }
            ],
            reason="covers watering",
            confidence=0.8,
        ),
        requested_aspects=["watering_frequency_or_trigger", "toxicity_pet_safety"],
    )
    assert result.status == "partial"
    assert result.answerable is False
    assert "toxicity_pet_safety" in result.missing_aspects

async def test_safety_threshold_applies_to_toxicity_aspects() -> None:
    from app.assistant.graph import _validate_evidence_against_required_aspects
    result = _validate_evidence_against_required_aspects(
        {
            "required_aspects": ["toxicity_pet_safety"],
        },
        evidence="The plant is toxic to cats.",
        semantic_result=AnswerabilityResult(
            status="full",
            answerable=True,
            covered_aspects=["toxicity_pet_safety"],
            source_support=[
                {
                    "claim": "Toxic to cats.",
                    "source_urls": ["https://example.org/toxic"],
                    "covered_aspects": ["toxicity_pet_safety"],
                    "evidence_quote": "toxic to cats",
                    "confidence": 0.9,
                }
            ],
            confidence=0.9,
        ),
        threshold=0.75,
        safety_threshold=0.85,
        strong_threshold=0.30,
    )
    assert result.answerable is True
    assert any(a.value == "toxicity_pet_safety" for a in result.covered_aspects)

async def test_web_query_converts_domain_qualified_aspects_to_natural_language() -> None:
    query = _targeted_web_query(
        "Monstera deliciosa",
        ["pest_treatment_action", "pest_identification"],
        "pests",
        "How do I treat pests on my Monstera?",
    )
    assert "pest treatment and control" in query
    assert "pest identification" in query
    assert "Monstera deliciosa" in query

async def test_web_query_diagnosis_aspects_produce_useful_terms() -> None:
    query = _targeted_web_query(
        "Ficus lyrata",
        ["diagnosis_leaf_color_change_causes"],
        "diagnosis",
        "Why are my leaves yellow?",
    )
    assert "leaf color change causes" in query
    assert "Ficus lyrata" in query

async def test_diagnostics_expose_expanded_canonical_values() -> None:
    tools = FakeTools(
        classifier_data={
            "language": "en",
            "answer_language": "en",
            "intent": "plant_care_question",
            "topic": "toxicity_safety",
            "required_aspects": ["toxicity_pet_safety"],
            "plant_reference": "Pata",
            "confidence": 0.92,
            "needs_retrieval": True,
        }
    )
    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="Is my Pata safe for pets?",
        plant_hint=None,
    )
    diagnostics = result.get("diagnostics", {})
    assert diagnostics.get("topic") == "toxicity_safety"
    assert "toxicity_pet_safety" in diagnostics.get("required_aspects", [])
    assert "pet_toxicity" not in diagnostics.get("required_aspects", [])

async def test_legacy_aspect_translation_in_state() -> None:
    from app.assistant.graph import _required_aspects_from_state
    aspects = _required_aspects_from_state({"required_aspects": ["pet_toxicity"]})
    assert len(aspects) == 1
    assert aspects[0].value == "toxicity_pet_safety"

async def test_legacy_topic_translation_in_state() -> None:
    from app.assistant.graph import _final_required_aspect_values
    values = _final_required_aspect_values({"required_aspects": ["fertilizer_frequency"]})
    assert "nutrition_feeding_schedule" in values

async def test_broad_care_uses_general_aspect() -> None:
    tools = FakeTools(
        classifier_data={
            "language": "en",
            "answer_language": "en",
            "intent": "plant_care_question",
            "topic": "general_care",
            "required_aspects": ["general_care_summary"],
            "plant_reference": "Pata",
            "confidence": 0.92,
            "needs_retrieval": True,
        }
    )
    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="Dame consejos generales para cuidar mi Pata",
        plant_hint=None,
    )
    assert result["topic"] == "general_care"
    assert "general_care_summary" in result["required_aspects"]

async def test_expanded_aspect_values_in_answerability_prompt() -> None:
    from app.assistant.graph import _grounded_answer_prompt
    prompt = _grounded_answer_prompt(
        user_message="Is this safe for cats?",
        plant_name="Pothos",
        topic="toxicity_safety",
        evidence_type="rag",
        evidence="Evidence about pet safety.",
        limitations=[],
        source_metadata=[],
        extra_context="",
        required_aspects=["toxicity_pet_safety"],
        covered_aspects=["toxicity_pet_safety"],
        missing_aspects=[],
    )
    assert "toxicity_pet_safety" in prompt
    assert "toxicity_safety" in prompt

async def test_non_english_snippet_reaches_judge_without_keyword_filter() -> None:
    """Regression: deterministic keyword matching MUST NOT gate evidence eligibility.

    Non-English snippets without any English keywords must still reach the
    answerability judge. The judge decides coverage, not keyword matching.
    """
    tools = FakeTools(
        rag_answerable=False,
        plant_data=None,
        web_results=[
            SearchResult(
                title="Guia de seguridad para mascotas",
                url="https://example.org/seguridad-mascotas",
                snippet="Planta toxica para gatos y perros. Mantener fuera del alcance.",
                source_domain="example.org",
            )
        ],
    )

    await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="Es segura para mascotas mi Pata?",
        plant_hint=None,
        plant_binomial_name=CONFIRMED_BINOMIAL,
    )

    assert tools.web_search_calls == 1
    judge_calls = [
        c for c in tools.judge_calls
        if c["payload"].get("evidence_type") == "combined_rag_web"
    ]
    assert len(judge_calls) >= 1
    judge_payload = judge_calls[0]["payload"]
    evidence_text = judge_payload.get("evidence", "")
    assert "toxica" in evidence_text.lower() or "mascotas" in evidence_text.lower()


# ---------------------------------------------------------------------------
# Deterministic prose removal tests
# ---------------------------------------------------------------------------

async def test_no_deterministic_emergency_prose_on_total_generation_failure() -> None:
    """When all model providers fail, no deterministic prose is returned."""
    tools = FakeTools(fail_model=True)

    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="How often should I water my Pata?",
        plant_hint=None,
    )

    assert result.get("total_generation_failure") is True
    assert not result.get("answer")
    assert "I could not generate" not in (result.get("answer") or "")
    assert "Try again" not in (result.get("answer") or "")

async def test_rag_fallback_does_not_return_prewritten_prose() -> None:
    """RAG fallback must not return prewritten prose as final assistant content."""
    tools = FakeTools(rag_answerable=False, plant_data=None, web_results=[])

    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="How often should I water my Pata?",
        plant_hint=None,
        plant_binomial_name=CONFIRMED_BINOMIAL,
    )

    answer = result.get("answer", "")
    assert "A practical guide is:" not in answer
    assert "For" != answer[:3]

async def test_all_models_failed_returns_retryable_signal() -> None:
    """When all model providers fail, the graph signals total generation failure."""
    tools = FakeTools(fail_model=True)

    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="How often should I water my Pata?",
        plant_hint=None,
    )

    assert result.get("total_generation_failure") is True
    assert not result.get("answer")

async def test_total_generation_failure_does_not_assign_answer() -> None:
    """Total generation failure must not assign any answer to the state."""
    tools = FakeTools(fail_model=True)

    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="How often should I water my Pata?",
        plant_hint=None,
    )

    assert "answer" not in result or not result["answer"]
    assert result.get("total_generation_failure") is True
