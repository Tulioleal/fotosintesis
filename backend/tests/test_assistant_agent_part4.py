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

async def test_assistant_uses_scientific_name_when_binomial_is_missing() -> None:
    tools = FakeTools(
        degraded_knowledge=True,
        plant_data=_structured_evidence(),
        web_results=[
            SearchResult(
                title="Trusted watering guide",
                url="https://example.org/watering",
                snippet="Water after the substrate dries.",
                source_domain="example.org",
            )
        ],
    )
    await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="How do I water this plant?",
        plant_hint="Tomato",
        plant_scientific_name="Solanum lycopersicum var. cerasiforme",
    )

    assert tools.knowledge_search_kwargs["scientific_name"] == "Solanum lycopersicum"
    assert tools.plant_data_kwargs is None

async def test_assistant_does_not_use_legacy_plant_for_care_evidence_operations() -> None:
    tools = FakeTools(degraded_knowledge=True, plant_data=_structured_evidence())
    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="How do I water this plant?",
        plant_hint="Potus",
    )

    assert tools.knowledge_search_kwargs is None
    assert tools.plant_data_kwargs is None
    assert "confirmed scientific name" in result["answer"]

async def test_assistant_ignores_blank_taxonomy_values_for_name_priority() -> None:
    tools = FakeTools(degraded_knowledge=True, plant_data=_structured_evidence())
    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="How do I water this plant?",
        plant_hint="Potus",
        plant_binomial_name="  ",
        plant_scientific_name="",
    )

    assert tools.knowledge_search_kwargs is None
    assert "confirmed scientific name" in result["answer"]

async def test_assistant_answers_degraded_knowledge_with_web_results() -> None:
    tools = FakeTools(
        degraded_knowledge=True,
        web_results=[
            SearchResult(
                title="Trusted watering guide",
                url="https://example.org/watering",
                snippet="Water when the substrate dries and avoid standing water.",
                source_domain="example.org",
            )
        ],
    )
    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="How do I water my Pata?",
        plant_hint=None,
        plant_binomial_name=CONFIRMED_BINOMIAL,
    )

    assert tools.web_search_calls == 1
    assert result["answer"] == "Synthesized model response."
    assert tools.model_calls == 1
    assert "have not yet been incorporated into the persisted knowledge" in tools.model_prompts[0]
    assert "Water when the substrate dries" in tools.model_prompts[0]
    assert result["sources"][0]["url"] == "https://example.org/watering"
    assert result["sources"][0]["evidence_type"] == "live_web"
    assert result["sources"][0]["confidence"] == 1.0
    assert tools.ingestion_calls == 0
    assert result["ingestion_claims"][0]["scientific_name"] == "Cotyledon tomentosa"
    assert result["ingestion_claims"][0]["topic"] == "watering"
    assert result["ingestion_claims"][0]["covered_aspects"] == ["watering_frequency_or_trigger"]

async def test_validated_web_metadata_uses_validation_confidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_judge_answerability(*args, **kwargs):
        return AnswerabilityResult(
            status="full",
            answerable=True,
            covered_aspects=["watering_frequency_or_trigger"],
            source_support=[
                {
                    "claim": "Watering guidance is directly supported.",
                    "source_urls": ["https://example.org/watering"],
                    "covered_aspects": ["watering_frequency_or_trigger"],
                    "evidence_quote": "Water when the substrate dries.",
                    "confidence": 0.82,
                }
            ],
            confidence=0.82,
        )

    monkeypatch.setattr(
        "app.assistant.graph.answerability._judge_answerability",
        fake_judge_answerability,
    )
    tools = FakeTools(
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

    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="How do I water my Pata?",
        plant_hint=None,
        plant_binomial_name=CONFIRMED_BINOMIAL,
    )

    assert result["ingestion_claims"][0]["confidence"] == 0.82
    assert result["sources"][0]["confidence"] == 0.82

async def test_web_fallback_excludes_off_aspect_trusted_source_from_prompt_sources_and_ingestion() -> None:
    tools = FakeTools(
        degraded_knowledge=True,
        web_results=[
            SearchResult(
                title="Trusted watering guide",
                url="https://example.org/watering",
                snippet="Water when the substrate dries before watering again.",
                source_domain="example.org",
            ),
            SearchResult(
                title="Trusted light guide",
                url="https://example.org/light",
                snippet="Provide bright indirect light and avoid harsh sun.",
                source_domain="example.org",
            ),
        ],
    )

    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="How do I water my Pata?",
        plant_hint=None,
        plant_binomial_name=CONFIRMED_BINOMIAL,
    )

    prompt = tools.model_prompts[0]
    assert "Water when the substrate dries" in prompt
    assert "bright indirect light" not in prompt
    assert [source["url"] for source in result["sources"]] == ["https://example.org/watering"]
    assert result["ingestion_claims"][0]["source_url"] == "https://example.org/watering"
    assert result["ingestion_claims"][0]["covered_aspects"] == ["watering_frequency_or_trigger"]
    assert result["ingestion_claims"][0]["confidence"] == 1.0

async def test_web_fallback_uses_minimum_confidence_across_validated_sources() -> None:
    tools = FakeTools(
        degraded_knowledge=True,
        judge_scores=[0.91, 0.83],
        classifier_data={
            "language": "en",
            "answer_language": "en",
            "intent": "plant_care_question",
            "topic": "watering",
            "required_aspects": ["watering_frequency_or_trigger", "light_exposure"],
            "plant_reference": "Pata",
            "confidence": 0.95,
            "needs_retrieval": True,
        },
        web_results=[
            SearchResult(
                title="Trusted watering guide",
                url="https://example.org/watering",
                snippet="Water when the substrate dries before watering again.",
                source_domain="example.org",
            ),
            SearchResult(
                title="Trusted light guide",
                url="https://example.org/light",
                snippet="Provide bright indirect light and avoid harsh sun.",
                source_domain="example.org",
            ),
        ],
    )

    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="How do I water my Pata and how much light does it need?",
        plant_hint=None,
        plant_binomial_name=CONFIRMED_BINOMIAL,
    )

    assert result["web_validation_confidence"] == 0.91
    assert result["sources"][0]["confidence"] == 0.91
    assert tools.judge_calls[-1]["payload"]["evidence_type"] == "combined_rag_web"

async def test_partial_judge_result_keeps_only_supported_sources_for_ingestion() -> None:
    class PartialJudgeTools(FakeTools):
        async def judge_response(self, payload: dict, rubric: dict, **kwargs) -> object:
            self.judge_calls.append({"payload": payload, "rubric": rubric})
            if payload.get("evidence_type") == "combined_rag_web":
                return JudgeResult.from_provider_data(
                    provider="test-judge",
                    model="test-model",
                    passing_score=1.0,
                    data={
                        "status": "partial",
                        "covered_aspects": ["watering_frequency_or_trigger"],
                        "missing_aspects": ["light_exposure"],
                        "source_support": [
                            {
                                "claim": "Water when the substrate dries.",
                                "source_urls": ["https://example.org/watering"],
                                "covered_aspects": ["watering_frequency_or_trigger"],
                                "evidence_quote": "Water when the substrate dries.",
                                "confidence": 0.86,
                            }
                        ],
                        "contradictions": [],
                        "confidence": 0.86,
                        "score": 0.86,
                        "passed": False,
                        "reasons": ["only watering is directly supported"],
                    },
                )
            return await super().judge_response(payload, rubric, **kwargs)

    tools = PartialJudgeTools(
        degraded_knowledge=True,
        classifier_data={
            "language": "en",
            "answer_language": "en",
            "intent": "plant_care_question",
            "topic": "watering",
            "required_aspects": ["watering_frequency_or_trigger", "light_exposure"],
            "plant_reference": "Pata",
            "confidence": 0.95,
            "needs_retrieval": True,
        },
        web_results=[
            SearchResult(
                title="Trusted watering guide",
                url="https://example.org/watering",
                snippet="Water when the substrate dries before watering again.",
                source_domain="example.org",
            ),
            SearchResult(
                title="Trusted light guide",
                url="https://example.org/light",
                snippet="Provide bright indirect light and avoid harsh sun.",
                source_domain="example.org",
            ),
        ],
    )

    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="How do I water my Pata and how much light does it need?",
        plant_hint=None,
        plant_binomial_name=CONFIRMED_BINOMIAL,
    )

    assert result["answerability_status"] == "partial"
    assert result["sufficient"] is False
    assert result["covered_aspects"] == ["watering_frequency_or_trigger"]
    assert result["missing_aspects"] == ["light_exposure"]
    assert tools.judge_calls[-1]["payload"]["required_aspects"] == [
        "watering_frequency_or_trigger",
        "light_exposure",
    ]
    assert tools.judge_calls[-1]["payload"]["rag_answerability"]["status"] == "insufficient"
    assert [source["url"] for source in result["sources"]] == ["https://example.org/watering"]
    assert result["ingestion_claims"][0]["source_url"] == "https://example.org/watering"
    assert result["ingestion_claims"][0]["covered_aspects"] == ["watering_frequency_or_trigger"]
    assert "https://example.org/light" not in tools.model_prompts[0]

async def test_combined_web_answer_uses_supported_rag_and_web_evidence() -> None:
    class CombinedJudgeTools(FakeTools):
        async def judge_response(self, payload: dict, rubric: dict, **kwargs) -> object:
            self.judge_calls.append({"payload": payload, "rubric": rubric})
            if payload.get("evidence_type") == "rag":
                return JudgeResult.from_provider_data(
                    provider="test-judge",
                    model="test-model",
                    passing_score=1.0,
                    data={
                        "status": "partial",
                        "covered_aspects": ["watering_frequency_or_trigger"],
                        "missing_aspects": ["light_exposure"],
                        "source_support": [
                            {
                                "claim": "Moderate watering with well-draining substrate.",
                                "source_urls": ["https://example.org/source"],
                                "covered_aspects": ["watering_frequency_or_trigger"],
                                "evidence_quote": "Requires moderate watering and well-draining substrate.",
                                "confidence": 0.86,
                            }
                        ],
                        "contradictions": [],
                        "confidence": 0.86,
                        "score": 0.86,
                        "passed": False,
                        "reasons": ["RAG only supports watering."],
                    },
                )
            if payload.get("evidence_type") == "combined_rag_web":
                return JudgeResult.from_provider_data(
                    provider="test-judge",
                    model="test-model",
                    passing_score=1.0,
                    data={
                        "status": "full",
                        "covered_aspects": ["watering_frequency_or_trigger", "light_exposure"],
                        "missing_aspects": [],
                        "source_support": [
                            {
                                "claim": "Moderate watering with well-draining substrate.",
                                "source_urls": ["https://example.org/source"],
                                "covered_aspects": ["watering_frequency_or_trigger"],
                                "evidence_quote": "Requires moderate watering and well-draining substrate.",
                                "confidence": 0.88,
                            },
                            {
                                "claim": "Luz indirecta brillante.",
                                "source_urls": ["https://example.org/light"],
                                "covered_aspects": ["light_exposure"],
                                "evidence_quote": "Provide bright indirect light.",
                                "confidence": 0.88,
                            },
                        ],
                        "contradictions": [],
                        "confidence": 0.88,
                        "score": 0.88,
                        "passed": True,
                        "reasons": [],
                    },
                )
            return await super().judge_response(payload, rubric, **kwargs)

    tools = CombinedJudgeTools(
        classifier_data={
            "language": "en",
            "answer_language": "en",
            "intent": "plant_care_question",
            "topic": "watering",
            "required_aspects": ["watering_frequency_or_trigger", "light_exposure"],
            "plant_reference": "Pata",
            "confidence": 0.95,
            "needs_retrieval": True,
        },
        web_results=[
            SearchResult(
                title="Trusted light guide",
                url="https://example.org/light",
                snippet="Provide bright indirect light.",
                source_domain="example.org",
            )
        ],
    )

    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="How do I water my Pata and how much light does it need?",
        plant_hint=None,
        plant_binomial_name=CONFIRMED_BINOMIAL,
    )

    combined_payload = tools.judge_calls[-1]["payload"]
    assert combined_payload["required_aspects"] == [
        "watering_frequency_or_trigger",
        "light_exposure",
    ]
    assert combined_payload["rag_answerability"]["status"] == "partial"
    assert "Requires moderate watering" in combined_payload["evidence"]
    assert result["answerability_status"] == "full"
    assert result["covered_aspects"] == ["watering_frequency_or_trigger", "light_exposure"]
    assert result["missing_aspects"] == []
    assert "Evidence type: combined_rag_web" in tools.model_prompts[0]
    assert "Requires moderate watering" in tools.model_prompts[0]
    assert "Provide bright indirect light" in tools.model_prompts[0]

async def test_low_confidence_partial_web_judge_keeps_supported_aspect() -> None:
    class LowConfidencePartialJudgeTools(FakeTools):
        async def judge_response(self, payload: dict, rubric: dict, **kwargs) -> object:
            self.judge_calls.append({"payload": payload, "rubric": rubric})
            if payload.get("evidence_type") == "combined_rag_web":
                return JudgeResult.from_provider_data(
                    provider="test-judge",
                    model="test-model",
                    passing_score=1.0,
                    data={
                        "status": "partial",
                        "covered_aspects": ["watering_frequency_or_trigger"],
                        "missing_aspects": ["light_exposure"],
                        "source_support": [
                            {
                                "claim": "Water when the substrate dries.",
                                "source_urls": ["https://example.org/watering"],
                                "covered_aspects": ["watering_frequency_or_trigger"],
                                "evidence_quote": "Water when the substrate dries.",
                                "confidence": 0.6,
                            }
                        ],
                        "contradictions": [],
                        "confidence": 0.6,
                        "score": 0.6,
                        "passed": False,
                        "reasons": ["only low-confidence watering support was found"],
                    },
                )
            return await super().judge_response(payload, rubric, **kwargs)

    tools = LowConfidencePartialJudgeTools(
        degraded_knowledge=True,
        classifier_data={
            "language": "en",
            "answer_language": "en",
            "intent": "plant_care_question",
            "topic": "watering",
            "required_aspects": ["watering_frequency_or_trigger", "light_exposure"],
            "plant_reference": "Pata",
            "confidence": 0.95,
            "needs_retrieval": True,
        },
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
        message="How do I water my Pata and how much light does it need?",
        plant_hint=None,
        plant_binomial_name=CONFIRMED_BINOMIAL,
    )

    assert result["answerability_status"] == "partial"
    assert result["sufficient"] is False
    assert result["covered_aspects"] == ["watering_frequency_or_trigger"]
    assert result["missing_aspects"] == ["light_exposure"]
    assert result["web_validation_confidence"] == 0.6

async def test_insufficient_judge_result_blocks_web_answer_and_ingestion() -> None:
    class InsufficientJudgeTools(FakeTools):
        async def judge_response(self, payload: dict, rubric: dict, **kwargs) -> object:
            self.judge_calls.append({"payload": payload, "rubric": rubric})
            if payload.get("evidence_type") == "combined_rag_web":
                return JudgeResult.from_provider_data(
                    provider="test-judge",
                    model="test-model",
                    passing_score=1.0,
                    data={
                        "status": "insufficient",
                        "covered_aspects": [],
                        "missing_aspects": ["watering_frequency_or_trigger"],
                        "source_support": [],
                        "contradictions": [],
                        "confidence": 0.34,
                        "score": 0.34,
                        "passed": False,
                        "reasons": ["web evidence does not directly answer watering frequency"],
                    },
                )
            return await super().judge_response(payload, rubric, **kwargs)

    tools = InsufficientJudgeTools(
        degraded_knowledge=True,
        web_results=[
            SearchResult(
                title="Generic care guide",
                url="https://example.org/generic",
                snippet="This plant is a succulent.",
                source_domain="example.org",
            )
        ],
    )

    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="How do I water my Pata?",
        plant_hint=None,
        plant_binomial_name=CONFIRMED_BINOMIAL,
    )

    assert result["answerability_status"] == "insufficient"
    assert result.get("web_results", []) == []
    assert result.get("ingestion_claims", []) == []
    assert result["source_support"] == []
    assert result["missing_aspects"] == ["watering_frequency_or_trigger"]
    assert "web_search_not_validated" in result["fallback_reasons"]

async def test_fetched_web_content_is_passed_to_combined_judge() -> None:
    tools = FakeTools(
        degraded_knowledge=True,
        web_results=[
            TrustedPageEvidence(
                result=SearchResult(
                    title="Trusted watering guide",
                    url="https://example.org/watering",
                    snippet="Generic plant page.",
                    source_domain="example.org",
                ),
                content="Water when the substrate dries before watering again.",
                fetch_status="fetched",
                fetched_content_length=53,
            )
        ],
    )

    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="How do I water my Pata?",
        plant_hint=None,
        plant_binomial_name=CONFIRMED_BINOMIAL,
    )

    combined_payloads = [
        call["payload"] for call in tools.judge_calls if call["payload"].get("evidence_type") == "combined_rag_web"
    ]
    assert combined_payloads
    assert "Water when the substrate dries" in combined_payloads[0]["evidence"]
    assert result["answerability_status"] == "full"

async def test_low_confidence_full_web_support_is_not_blocked_for_non_safety() -> None:
    class LowConfidenceFullJudgeTools(FakeTools):
        async def judge_response(self, payload: dict, rubric: dict, **kwargs) -> object:
            self.judge_calls.append({"payload": payload, "rubric": rubric})
            if payload.get("evidence_type") == "combined_rag_web":
                return JudgeResult.from_provider_data(
                    provider="test-judge",
                    model="test-model",
                    data={
                        "status": "full",
                        "covered_aspects": ["watering_frequency_or_trigger"],
                        "missing_aspects": [],
                        "source_support": [
                            {
                                "claim": "Water when the substrate dries.",
                                "source_urls": ["https://example.org/watering"],
                                "covered_aspects": ["watering_frequency_or_trigger"],
                                "evidence_quote": "Water when the substrate dries.",
                                "confidence": 0.2,
                            }
                        ],
                        "contradictions": [],
                        "confidence": 0.2,
                        "score": 0.2,
                        "passed": True,
                    },
                )
            return await super().judge_response(payload, rubric, **kwargs)

    tools = LowConfidenceFullJudgeTools(
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

    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="How do I water my Pata?",
        plant_hint=None,
        plant_binomial_name=CONFIRMED_BINOMIAL,
    )

    assert result["answerability_status"] == "full"
    assert result["covered_aspects"] == ["watering_frequency_or_trigger"]
    assert result["web_validation_confidence"] == 0.2

async def test_low_confidence_safety_web_support_is_rejected() -> None:
    class LowConfidenceSafetyJudgeTools(FakeTools):
        async def judge_response(self, payload: dict, rubric: dict, **kwargs) -> object:
            self.judge_calls.append({"payload": payload, "rubric": rubric})
            if payload.get("evidence_type") == "combined_rag_web":
                return JudgeResult.from_provider_data(
                    provider="test-judge",
                    model="test-model",
                    data={
                        "status": "full",
                        "covered_aspects": ["toxicity_pet_safety"],
                        "missing_aspects": [],
                        "source_support": [
                            {
                                "claim": "This plant is toxic to pets.",
                                "source_urls": ["https://example.org/pets"],
                                "covered_aspects": ["toxicity_pet_safety"],
                                "evidence_quote": "toxic to pets",
                                "confidence": 0.2,
                            }
                        ],
                        "contradictions": [],
                        "confidence": 0.2,
                        "score": 0.2,
                        "passed": True,
                    },
                )
            return await super().judge_response(payload, rubric, **kwargs)

    tools = LowConfidenceSafetyJudgeTools(
        degraded_knowledge=True,
        classifier_data={
            "language": "en",
            "answer_language": "en",
            "intent": "plant_care_question",
            "topic": "toxicity_safety",
            "required_aspects": ["toxicity_pet_safety"],
            "plant_reference": "Pata",
            "confidence": 0.95,
            "needs_retrieval": True,
        },
        web_results=[
            SearchResult(
                title="Trusted pet guide",
                url="https://example.org/pets",
                snippet="This plant is toxic to pets.",
                source_domain="example.org",
            )
        ],
    )

    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="Is my Pata toxic to pets?",
        plant_hint=None,
        plant_binomial_name=CONFIRMED_BINOMIAL,
    )

    assert result["answerability_status"] == "insufficient"
    assert result["covered_aspects"] == []
    assert result["missing_aspects"] == ["toxicity_pet_safety"]

async def test_assistant_reuses_acquisition_search_candidates() -> None:
    class CandidateTools(FakeTools):
        async def knowledge_search(self, **kwargs) -> ToolResult:
            self.call_order.append("rag")
            self.knowledge_search_kwargs = kwargs
            return ToolResult(
                ok=True,
                data=KnowledgeAcquisitionResult(
                    status=AcquisitionStatus.degraded,
                    chunks=[],
                    limitations=["No trusted approved source was found."],
                    search_candidates=[
                        SearchResult(
                            title="Trusted watering guide",
                            url="https://example.org/watering",
                            snippet="Water when the substrate dries.",
                            source_domain="example.org",
                        )
                    ],
                ),
            )

    tools = CandidateTools(web_results=[])

    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="How do I water my Pata?",
        plant_hint=None,
        plant_binomial_name=CONFIRMED_BINOMIAL,
    )

    assert result["answerability_status"] == "full"
    assert tools.call_order == ["rag", "web"]
    assert tools.web_search_calls == 0

async def test_web_fallback_logs_diagnostic_fields(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="app.assistant.graph")
    tools = FakeTools(
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
        message="How do I water my Pata?",
        plant_hint=None,
        plant_binomial_name=CONFIRMED_BINOMIAL,
    )

    messages = {record.message for record in caplog.records}
    assert "assistant web fallback query prepared" in messages
    assert "assistant web search candidates selected" in messages
    assert "assistant web evidence selected" in messages
    assert "assistant web judge evidence prepared" in messages
    query_record = next(record for record in caplog.records if record.message == "assistant web fallback query prepared")
    assert getattr(query_record, "ctx_query") == tools.web_search_query
    assert "test-key" not in str(caplog.records)

async def test_contradictory_judge_result_links_conflicts_and_skips_ingestion() -> None:
    class ContradictoryJudgeTools(FakeTools):
        async def judge_response(self, payload: dict, rubric: dict, **kwargs) -> object:
            self.judge_calls.append({"payload": payload, "rubric": rubric})
            if payload.get("evidence_type") == "combined_rag_web":
                return JudgeResult.from_provider_data(
                    provider="test-judge",
                    model="test-model",
                    passing_score=1.0,
                    data={
                        "status": "contradictory",
                        "covered_aspects": ["watering_frequency_or_trigger"],
                        "missing_aspects": ["watering_frequency_or_trigger"],
                        "source_support": [],
                        "contradictions": [
                            {
                                "claim_a": "Water weekly.",
                                "claim_b": "Water monthly.",
                                "source_a_urls": ["https://example.org/watering-weekly"],
                                "source_b_urls": ["https://example.org/watering-monthly"],
                            }
                        ],
                        "confidence": 0.88,
                        "score": 0.88,
                        "passed": False,
                        "reasons": ["trusted sources conflict on watering frequency"],
                    },
                )
            return await super().judge_response(payload, rubric, **kwargs)

    answer = (
        "There are conflicting trusted sources: https://example.org/watering-weekly "
        "says water weekly and https://example.org/watering-monthly says water monthly."
    )
    tools = ContradictoryJudgeTools(
        degraded_knowledge=True,
        model_response=answer,
        web_results=[
            SearchResult(
                title="Weekly watering guide",
                url="https://example.org/watering-weekly",
                snippet="Water weekly.",
                source_domain="example.org",
            ),
            SearchResult(
                title="Monthly watering guide",
                url="https://example.org/watering-monthly",
                snippet="Water monthly.",
                source_domain="example.org",
            ),
        ],
    )

    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="How do I water my Pata?",
        plant_hint=None,
        plant_binomial_name=CONFIRMED_BINOMIAL,
    )

    assert result["answerability_status"] == "contradictory"
    assert result["ingestion_claims"] == []
    assert result["answer"] == answer
    assert "https://example.org/watering-weekly" in result["answer"]
    assert "https://example.org/watering-monthly" in result["answer"]
    assert "https://example.org/watering-weekly" in tools.model_prompts[0]
    assert "https://example.org/watering-monthly" in tools.model_prompts[0]

async def test_web_search_is_called_only_for_missing_aspects_after_rag_validation() -> None:
    tools = FakeTools(
        classifier_data={
            "language": "en",
            "answer_language": "en",
            "intent": "plant_care_question",
            "topic": "watering",
            "required_aspects": ["watering_frequency_or_trigger", "light_exposure"],
            "plant_reference": "Pata",
            "confidence": 0.95,
            "needs_retrieval": True,
        },
        web_results=[
            SearchResult(
                title="Trusted light guide",
                url="https://example.org/light",
                snippet="Provide bright indirect light.",
                source_domain="example.org",
            )
        ],
    )

    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="How often should I water my Pata and how much light does it need?",
        plant_hint=None,
        plant_binomial_name=CONFIRMED_BINOMIAL,
    )

    assert tools.web_search_calls == 0
    assert result["covered_aspects"] == ["watering_frequency_or_trigger", "light_exposure"]
    assert result["evidence_path"] == ["rag"]

async def test_failed_multi_aspect_rag_judge_preserves_direct_local_coverage() -> None:
    class FailedHighConfidenceRagTools(FakeTools):
        async def judge_response(self, payload: dict, rubric: dict, **kwargs) -> object:
            self.judge_calls.append({"payload": payload, "rubric": rubric})
            if payload.get("evidence_type") == "rag":
                return SimpleNamespace(
                    score=0.91,
                    passed=False,
                    reasons=["rag evidence does not answer the full multi-aspect question"],
                )
            return await super().judge_response(payload, rubric, **kwargs)

    tools = FailedHighConfidenceRagTools(
        classifier_data={
            "language": "en",
            "answer_language": "en",
            "intent": "plant_care_question",
            "topic": "watering",
            "required_aspects": ["watering_frequency_or_trigger", "light_exposure"],
            "plant_reference": "Pata",
            "confidence": 0.95,
            "needs_retrieval": True,
        },
        knowledge_content="Water when the substrate dries between watering. No exposure guidance here.",
        web_results=[
            SearchResult(
                title="Trusted light guide",
                url="https://example.org/light",
                snippet="Provide bright indirect light.",
                source_domain="example.org",
            )
        ],
    )

    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="How often should I water my Pata and how much light does it need?",
        plant_hint=None,
        plant_binomial_name=CONFIRMED_BINOMIAL,
    )

    assert tools.web_search_calls == 1
    assert "light exposure" in tools.web_search_query
    assert "watering frequency" in tools.web_search_query
    assert result["covered_aspects"] == ["watering_frequency_or_trigger", "light_exposure"]
    assert result["evidence_path"] == ["web"]

async def test_web_fallback_query_preserves_original_question_context() -> None:
    tools = FakeTools(
        degraded_knowledge=True,
        classifier_data={
            "language": "en",
            "answer_language": "en",
            "intent": "plant_care_question",
            "topic": "watering",
            "required_aspects": ["watering_frequency_or_trigger"],
            "plant_reference": "Pata",
            "confidence": 0.95,
            "needs_retrieval": True,
        },
        web_results=[
            SearchResult(
                title="Trusted watering guide",
                url="https://example.org/watering",
                snippet="Water when the substrate dries before watering again.",
                source_domain="example.org",
            )
        ],
    )

    await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="Can I water my Pata with boiled water that has already cooled?",
        plant_hint=None,
        plant_binomial_name=CONFIRMED_BINOMIAL,
    )

    assert "Cotyledon tomentosa watering frequency" in tools.web_search_query
    assert "Can I water my Pata with boiled water that has already cooled?" in tools.web_search_query
    assert tools.web_search_query.endswith("houseplant care trusted source")
