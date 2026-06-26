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

async def test_failed_tool_action_is_not_claimed_complete() -> None:
    tools = FakeTools(
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
        },
    )
    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="Create a reminder for Pata on 2026-06-01 10:30 water weekly",
        plant_hint=None,
    )

    assert "not completed" in result["answer"].lower()
    assert result["tool_failures"]
    assert tools.model_calls == 1

async def test_reminder_missing_data_requires_confirmation() -> None:
    result = await AssistantGraph(
        FakeTools(
            classifier_data={
                "language": "en",
                "answer_language": "en",
                "intent": "reminder_request",
                "topic": "watering",
                "required_aspects": [],
                "plant_reference": "Pata",
                "confidence": 0.92,
                "needs_retrieval": False,
                "reminder_suggestion_requested": False,
            }
        )
    ).run(
        user_id=uuid4(),
        message="Remind me to water",
        plant_hint=None,
    )

    assert result["requires_confirmation"] is True
    assert "To create the reminder I need" in result["answer"]

async def test_reminder_date_only_requires_explicit_time() -> None:
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
            "reminder_suggestion_requested": False,
        }
    )
    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="Create a reminder for Pata on 2026-06-01 to water weekly",
        plant_hint=None,
    )

    assert result["requires_confirmation"] is True
    assert "To create the reminder I need" in result["answer"]
    assert tools.created_reminders == 0

async def test_reminder_missing_recurrence_defaults_to_none() -> None:
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
            "reminder_suggestion_requested": False,
        }
    )
    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="Create a reminder for Pata on 2026-06-01 10:30 to water",
        plant_hint=None,
    )

    assert result.get("answer")
    assert tools.created_reminders == 1
    assert tools.reminder_kwargs["recurrence"] == "none"

async def test_complete_reminder_creates_with_due_at_and_recurrence() -> None:
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
    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="Create a reminder for Pata on 2026-06-01 10:30 water weekly",
        plant_hint=None,
    )

    assert result.get("answer")
    assert tools.created_reminders == 1
    assert "reminder_suggestion" not in result
    assert tools.reminder_kwargs["due_at"] == datetime(2026, 6, 1, 10, 30, tzinfo=timezone.utc)
    assert tools.reminder_kwargs["recurrence"] == "weekly"
    fallback_prompts = [p for p in tools.model_prompts if "Render a fallback response" in p]
    assert any("reminder_created" in p for p in fallback_prompts)

async def test_complete_reminder_suggestion_returns_confirmation_payload() -> None:
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
            "reminder_suggestion_requested": True,
        }
    )
    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="Suggest a reminder for Pata on 2026-06-01 10:30 to water weekly",
        plant_hint=None,
    )

    assert result["requires_confirmation"] is True
    assert tools.created_reminders == 0
    assert result["reminder_suggestion"]["plant_name"] == "Pata"
    assert result["reminder_suggestion"]["action"] == "water"
    assert result["reminder_suggestion"]["due_at"] == datetime(
        2026, 6, 1, 10, 30, tzinfo=timezone.utc
    )
    assert result["reminder_suggestion"]["recurrence"] == "weekly"
    assert "assistant" in result["reminder_suggestion"]["suggestion_justification"]

def test_aspect_validation_guidance_returns_watering_trigger_for_watering_aspect() -> None:
    guidance = _aspect_validation_guidance(["watering_frequency_or_trigger"])

    assert "watering_frequency_or_trigger" in guidance
    assert "condition-based trigger" in guidance["watering_frequency_or_trigger"]
    assert "soil is dry" in guidance["watering_frequency_or_trigger"]
    assert "substrate dries" in guidance["watering_frequency_or_trigger"]

def test_aspect_validation_guidance_ignores_unknown_aspect() -> None:
    guidance = _aspect_validation_guidance(["light_exposure"])

    assert guidance == {}

def test_aspect_validation_guidance_ignores_unmapped_aspects() -> None:
    guidance = _aspect_validation_guidance(["unknown_aspect", "light_exposure"])

    assert guidance == {}

def test_aspect_validation_guidance_handles_mixed_known_and_unknown() -> None:
    guidance = _aspect_validation_guidance(["watering_frequency_or_trigger", "unknown_aspect"])

    assert len(guidance) == 1
    assert "watering_frequency_or_trigger" in guidance

def test_judge_payload_includes_metadata_watering_trigger_guidance() -> None:
    async def _run():
        class WateringGuidanceJudgeTools(FakeTools):
            async def judge_response(self, payload, rubric, **kwargs):
                self.judge_calls.append({"payload": payload, "rubric": rubric})
                return await super().judge_response(payload, rubric, **kwargs)

        tools = WateringGuidanceJudgeTools(
            degraded_knowledge=True,
            web_results=[
                SearchResult(
                    title="Trusted watering guide",
                    url="https://example.org/watering",
                    snippet="Water when the substrate dries.",
                    source_domain="example.org",
                )
            ],
        )

        await AssistantGraph(tools).run(
            user_id=uuid4(),
            message="How often should I water my Pata?",
            plant_hint=None,
            plant_binomial_name=CONFIRMED_BINOMIAL,
        )

        judge_payload = tools.judge_calls[-1]["payload"]
        judge_rubric = tools.judge_calls[-1]["rubric"]

        assert "aspect_validation_guidance" in judge_payload
        guidance = judge_payload["aspect_validation_guidance"]
        assert "watering_frequency_or_trigger" in guidance
        assert "condition-based trigger" in guidance["watering_frequency_or_trigger"]

        criteria_text = " ".join(judge_rubric["criteria"])
        assert "aspect_validation_guidance" in criteria_text
        assert "condition-based watering trigger" not in criteria_text

    import asyncio
    asyncio.get_event_loop().run_until_complete(_run())

async def test_validated_web_evidence_with_substrate_dry_trigger_becomes_answerable() -> None:
    class SubstrateDryJudgeTools(FakeTools):
        async def judge_response(self, payload, rubric, **kwargs):
            self.judge_calls.append({"payload": payload, "rubric": rubric})
            evidence = str(payload.get("evidence", "")).lower()
            guidance = payload.get("aspect_validation_guidance", {})
            required = list(payload.get("required_aspects") or [])
            if (
                "watering_frequency_or_trigger" in required
                and "watering_frequency_or_trigger" in guidance
                and ("substrate dries" in evidence or "soil is dry" in evidence or "soil dries" in evidence)
            ):
                return SimpleNamespace(
                    score=0.9,
                    passed=True,
                    status="full",
                    covered_aspects=["watering_frequency_or_trigger"],
                    missing_aspects=[],
                    source_support=[
                        {
                            "claim": "Water when the substrate dries.",
                            "source_urls": ["https://example.org/watering"],
                            "covered_aspects": ["watering_frequency_or_trigger"],
                            "evidence_quote": "Water when the substrate dries.",
                            "confidence": 0.9,
                        }
                    ],
                    contradictions=[],
                    confidence=0.9,
                    reasons=[],
                )
            return SimpleNamespace(
                score=0.0,
                passed=False,
                status="insufficient",
                covered_aspects=[],
                missing_aspects=required,
                source_support=[],
                contradictions=[],
                confidence=0.0,
                reasons=["evidence does not cover watering aspect"],
            )

    tools = SubstrateDryJudgeTools(
        degraded_knowledge=True,
        web_results=[
            SearchResult(
                title="Trusted watering guide",
                url="https://example.org/watering",
                snippet="Water when the substrate dries before watering again.",
                source_domain="example.org",
            )
        ],
    )

    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="How often should I water my Pata?",
        plant_hint=None,
        plant_binomial_name=CONFIRMED_BINOMIAL,
    )

    assert result["answerability_status"] == "full"
    assert "watering_frequency_or_trigger" in (result.get("covered_aspects") or [])
    assert result["covered_aspects"] == ["watering_frequency_or_trigger"]
    assert result["missing_aspects"] == []

async def test_generic_watering_text_still_fails_validation() -> None:
    class GenericWateringJudgeTools(FakeTools):
        async def judge_response(self, payload, rubric, **kwargs):
            self.judge_calls.append({"payload": payload, "rubric": rubric})
            evidence = str(payload.get("evidence", "")).lower()
            required = list(payload.get("required_aspects") or [])
            if "watering_frequency_or_trigger" in required:
                has_trigger = any(
                    term in evidence
                    for term in ["substrate dries", "soil is dry", "soil dries", "dry between watering", "dry before watering"]
                )
                if not has_trigger:
                    return SimpleNamespace(
                        score=0.0,
                        passed=False,
                        status="insufficient",
                        covered_aspects=[],
                        missing_aspects=["watering_frequency_or_trigger"],
                        source_support=[],
                        contradictions=[],
                        confidence=0.0,
                        reasons=["generic watering text does not cover watering trigger"],
                    )
            return await super().judge_response(payload, rubric, **kwargs)

    tools = GenericWateringJudgeTools(
        degraded_knowledge=True,
        web_results=[
            SearchResult(
                title="General care guide",
                url="https://example.org/care",
                snippet="This is a popular houseplant and needs moderate watering.",
                source_domain="example.org",
            )
        ],
    )

    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="How often should I water my Pata?",
        plant_hint=None,
        plant_binomial_name=CONFIRMED_BINOMIAL,
    )

    assert result["answerability_status"] != "full" or "watering_frequency_or_trigger" not in (result.get("covered_aspects") or [])

def test_targeted_web_query_does_not_expand_watering_frequency_terms() -> None:
    query = _targeted_web_query(
        "Epipremnum aureum",
        ["watering_frequency_or_trigger"],
        "watering",
        "How often should I water it?",
    )

    assert "watering frequency" in query
    assert "Epipremnum aureum" in query
    assert "How often should I water it?" in query

def test_targeted_web_query_converts_aspect_snake_case_to_words() -> None:
    query = _targeted_web_query(
        "Epipremnum aureum",
        ["light_exposure"],
        "light",
        "How much light does it need?",
    )

    assert "light exposure" in query
    assert "Epipremnum aureum" in query


# --- RAG contextual validation threshold regression tests ---

async def test_low_confidence_strong_watering_support_is_accepted() -> None:
    tools = StrongWateringJudgeTools()
    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="How often should I water my Pata?",
        plant_hint=None,
        plant_binomial_name=CONFIRMED_BINOMIAL,
    )

    assert result["sufficient"] is True
    assert "watering_frequency_or_trigger" in result.get("covered_aspects", [])
    assert result["answerability_status"] == "full"
    assert tools.web_search_calls == 0

async def test_low_confidence_safety_support_is_rejected() -> None:
    tools = LowConfidenceSafetyJudgeTools()
    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="Is my Pata toxic to pets?",
        plant_hint=None,
        plant_binomial_name=CONFIRMED_BINOMIAL,
    )

    assert result["sufficient"] is False
    assert "toxicity_pet_safety" in result.get("missing_aspects", [])
    assert "toxicity_pet_safety" not in result.get("covered_aspects", [])

async def test_partial_low_confidence_support_is_promoted_when_all_aspects_covered() -> None:
    tools = PartialLowConfidenceJudgeTools()
    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="How often should I water my Pata and how much light does it need?",
        plant_hint=None,
        plant_binomial_name=CONFIRMED_BINOMIAL,
    )

    assert result["sufficient"] is True
    assert "watering_frequency_or_trigger" in result.get("covered_aspects", [])
    assert "light_exposure" in result.get("covered_aspects", [])

async def test_high_confidence_partial_support_still_works_as_partial() -> None:
    tools = HighConfidencePartialJudgeTools()
    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="How often should I water my Pata and how much light does it need?",
        plant_hint=None,
        plant_binomial_name=CONFIRMED_BINOMIAL,
    )

    assert result["sufficient"] is False
    assert "watering_frequency_or_trigger" in result.get("covered_aspects", [])
    assert "light_exposure" in result.get("missing_aspects", [])

async def test_judge_timeout_returns_controlled_insufficient_result() -> None:
    from app.core.settings import Settings
    tools = SlowJudgeTools()
    settings = Settings(assistant_judge_timeout_seconds=0.1)
    result = await AssistantGraph(tools, settings=settings).run(
        user_id=uuid4(),
        message="How often should I water my Pata?",
        plant_hint=None,
        plant_binomial_name=CONFIRMED_BINOMIAL,
    )

    assert result["sufficient"] is False
    assert result["answerability_status"] == "insufficient"
    assert tools.web_search_calls == 1

