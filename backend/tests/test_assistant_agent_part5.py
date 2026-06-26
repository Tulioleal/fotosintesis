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

async def test_partial_non_critical_answer_when_only_some_aspects_validate() -> None:
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
        web_results=[],
    )

    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="How often should I water my Pata and how much light does it need?",
        plant_hint=None,
        plant_binomial_name=CONFIRMED_BINOMIAL,
    )

    assert result["answer"] == "Synthesized model response."
    assert result["covered_aspects"] == ["watering_frequency_or_trigger", "light_exposure"]
    assert result["missing_aspects"] == []
    assert "Unvalidated aspects: []" in tools.model_prompts[-1]

async def test_safety_sensitive_answer_refuses_partial_without_direct_evidence() -> None:
    tools = FakeTools(
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
        rag_answerable=False,
        web_results=[],
    )

    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="Is my Pata toxic to cats?",
        plant_hint=None,
        plant_binomial_name=CONFIRMED_BINOMIAL,
    )

    assert "As a precaution" in result["answer"]
    assert tools.model_calls == 1

async def test_safety_sensitive_answer_refuses_web_partial_without_safety_source() -> None:
    tools = FakeTools(
        classifier_data={
            "language": "en",
            "answer_language": "en",
            "intent": "plant_care_question",
            "topic": "toxicity_safety",
            "required_aspects": ["watering_frequency_or_trigger", "toxicity_pet_safety"],
            "plant_reference": "Pata",
            "confidence": 0.95,
            "needs_retrieval": True,
        },
        rag_answerable=False,
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
        message="How do I water my Pata and is it toxic to cats?",
        plant_hint=None,
        plant_binomial_name=CONFIRMED_BINOMIAL,
    )

    assert "As a precaution" in result["answer"]
    assert result["covered_aspects"] == ["watering_frequency_or_trigger"]
    assert result["missing_aspects"] == ["toxicity_pet_safety"]
    assert tools.model_calls == 1

async def test_diagnostic_metadata_includes_intent_topic_aspects_path_and_language() -> None:
    tools = FakeTools()

    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="How often should I water my Pata?",
        plant_hint=None,
        plant_binomial_name=CONFIRMED_BINOMIAL,
    )

    diagnostics = result["diagnostics"]
    assert diagnostics["intent"] == "plant_care_question"
    assert diagnostics["topic"] == "watering"
    assert diagnostics["required_aspects"] == ["watering_frequency_or_trigger"]
    assert diagnostics["covered_aspects"] == ["watering_frequency_or_trigger"]
    assert diagnostics["missing_aspects"] == []
    assert diagnostics["evidence_path"] == ["rag"]
    assert diagnostics["answer_language"] == "es"

async def test_assistant_fallback_answer_uses_fetched_page_content() -> None:
    tools = FakeTools(
        degraded_knowledge=True,
        web_results=[
            TrustedPageEvidence(
                result=SearchResult(
                    title="Trusted watering guide",
                    url="https://example.org/watering",
                    snippet="Short search snippet.",
                    source_domain="example.org",
                ),
                content="Full trusted page content says to water only after the substrate dries deeply.",
            )
        ],
    )
    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="How do I water my Pata?",
        plant_hint=None,
        plant_binomial_name=CONFIRMED_BINOMIAL,
    )

    assert result["answer"] == "Synthesized model response."
    assert "water only after the substrate dries deeply" in tools.model_prompts[0]
    assert "Short search snippet" not in tools.model_prompts[0]
    assert result["sources"][0]["url"] == "https://example.org/watering"
    assert result["ingestion_claims"][0]["source_url"] == "https://example.org/watering"

async def test_assistant_fallback_answer_degrades_to_snippet_when_fetch_fails() -> None:
    tools = FakeTools(
        degraded_knowledge=True,
        web_results=[
            TrustedPageEvidence(
                result=SearchResult(
                    title="Trusted watering guide",
                    url="https://example.org/watering",
                    snippet="Snippet says water when the soil is dry after checking the substrate.",
                    source_domain="example.org",
                ),
                error="unsupported content type",
            )
        ],
    )
    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="How do I water my Pata?",
        plant_hint=None,
        plant_binomial_name=CONFIRMED_BINOMIAL,
    )

    assert result["answer"] == "Synthesized model response."
    assert "Snippet says water when the soil is dry" in tools.model_prompts[0]
    assert "Evidence type: live_web" in tools.model_prompts[0]

async def test_trusted_web_search_called_after_rag_and_structured_not_answerable() -> None:
    tools = FakeTools(
        rag_answerable=False,
        plant_data=_structured_evidence(),
        structured_answerable=False,
        web_results=[
            SearchResult(
                title="Trusted toxicity guide",
                url="https://example.org/toxicity",
                snippet="Direct toxicity evidence from a trusted source.",
                source_domain="example.org",
            )
        ],
    )

    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="Es toxica para gatos mi Pata?",
        plant_hint=None,
        plant_binomial_name=CONFIRMED_BINOMIAL,
    )

    assert tools.call_order == ["rag", "web"]
    assert tools.plant_data_calls == 0
    assert tools.web_search_calls == 1
    assert "rag_not_answerable" in result["fallback_reasons"]
    assert "structured_not_answerable" not in result["fallback_reasons"]
    assert "web_search_used" in result["fallback_reasons"]

async def test_conservative_safety_fallback_for_pet_safety_without_direct_evidence() -> None:
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

    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="Is my Pata safe for pets?",
        plant_hint=None,
        plant_binomial_name=CONFIRMED_BINOMIAL,
    )

    assert tools.web_search_calls == 1
    assert tools.model_calls == 1
    assert "I did not find direct and reliable evidence" in result["answer"]
    assert "out of reach of pets" in result["answer"]
    assert "web_search_no_direct_answer" in result["fallback_reasons"]
    assert "conservative_safety_fallback" in result["fallback_reasons"]

async def test_conservative_safety_fallback_for_edibility_without_direct_evidence() -> None:
    tools = FakeTools(
        rag_answerable=False,
        plant_data=None,
        web_results=[],
        classifier_data={
            "language": "en",
            "answer_language": "en",
            "intent": "plant_care_question",
            "topic": "toxicity_safety",
            "required_aspects": ["toxicity_human_edibility"],
            "plant_reference": "Pata",
            "confidence": 0.92,
            "needs_retrieval": True,
        },
    )

    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="Is my Pata edible?",
        plant_hint=None,
        plant_binomial_name=CONFIRMED_BINOMIAL,
    )

    assert tools.web_search_calls == 1
    assert tools.model_calls == 1
    assert "whether it is edible" in result["answer"]
    assert "do not consume" in result["answer"]
    assert "conservative_safety_fallback" in result["fallback_reasons"]

async def test_fallback_reasons_recorded_for_internal_metadata() -> None:
    tools = FakeTools(
        degraded_knowledge=True,
        plant_data=_structured_evidence(sufficient=False),
        web_results=[],
    )

    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="How do I water my Pata?",
        plant_hint=None,
        plant_binomial_name=CONFIRMED_BINOMIAL,
    )

    assert result["fallback_reasons"] == [
        "web_search_used",
        "web_search_no_direct_answer",
    ]

async def test_answerability_and_fallback_logs_are_emitted(monkeypatch: pytest.MonkeyPatch) -> None:
    logs: list[tuple[str, dict]] = []

    def record_info(message: str, *, extra: dict) -> None:
        logs.append((message, extra))

    monkeypatch.setattr("app.assistant.graph.helpers.logger.info", record_info)
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

    assert any(
        message == "assistant intent classified"
        and extra["ctx_intent"] == "botanical"
        and extra["ctx_care_intent"] == "plant_care_question"
        and extra["ctx_topic"] == "toxicity_safety"
        and extra["ctx_required_aspects"] == ["toxicity_pet_safety"]
        and extra["ctx_answer_language"] == "en"
        and extra["ctx_needs_retrieval"] is True
        and extra["ctx_classification_confidence"] == 0.92
        and extra["ctx_classification_source"] == "llm"
        and extra["ctx_classification_fallback_reason"] is None
        and extra["ctx_trace_id"]
        for message, extra in logs
    )
    assert any(
        message == "assistant answerability judge requested"
        and extra["ctx_evidence_type"] == "rag"
        and extra["ctx_topic"] == "toxicity_safety"
        and extra["ctx_plant_name_present"] is True
        and extra["ctx_required_aspects"] == ["toxicity_pet_safety"]
        and extra["ctx_source_count"] == 1
        and extra["ctx_evidence_chars"] > 0
        and extra["ctx_has_extra_payload"] is False
        and extra["ctx_trace_id"]
        for message, extra in logs
    )
    assert any(
        message == "assistant answerability judge completed"
        and extra["ctx_evidence_type"] == "rag"
        and extra["ctx_status"] == "insufficient"
        and extra["ctx_answerable"] is False
        and extra["ctx_covered_aspects"] == []
        and extra["ctx_missing_aspects"] == ["toxicity_pet_safety"]
        and extra["ctx_judge_confidence"] == 0.0
        and extra["ctx_source_support_count"] == 0
        and extra["ctx_contradictions_count"] == 0
        and extra["ctx_trace_id"]
        for message, extra in logs
    )
    assert any(
        message == "assistant answerability decision"
        and extra["ctx_evidence_type"] == "rag"
        and extra["ctx_status"] == "insufficient"
        and extra["ctx_answerable"] is False
        and extra["ctx_covered_aspects"] == []
        and extra["ctx_missing_aspects"] == ["toxicity_pet_safety"]
        and extra["ctx_answerability_confidence"] == 0.0
        and extra["ctx_source_support_count"] == 0
        and extra["ctx_contradictions_count"] == 0
        and extra["ctx_fallback_reason"] == "rag_not_answerable"
        and extra["ctx_trace_id"]
        for message, extra in logs
    )
    assert any(
        message == "assistant fallback route" and extra["ctx_fallback_reason"] == "web_search_used"
        for message, extra in logs
    )

async def test_combined_evidence_judge_log_emitted(monkeypatch: pytest.MonkeyPatch) -> None:
    logs: list[tuple[str, dict]] = []

    def record_info(message: str, *, extra: dict) -> None:
        logs.append((message, extra))

    monkeypatch.setattr("app.assistant.graph.helpers.logger.info", record_info)
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

    assert any(
        message == "assistant combined evidence judge evaluated"
        and extra["ctx_required_aspects"] == ["watering_frequency_or_trigger"]
        and extra["ctx_rag_chunk_count"] == 0
        and extra["ctx_web_result_count"] == 1
        and extra["ctx_source_count"] >= 1
        and extra["ctx_semantic_status"] == "full"
        and extra["ctx_validated_status"] == "full"
        and extra["ctx_validated_confidence"] == 1.0
        and extra["ctx_validated_missing_aspects"] == []
        and extra["ctx_trace_id"]
        for message, extra in logs
    )

async def test_assistant_preserves_limitations_when_web_search_fails() -> None:
    tools = FakeTools(degraded_knowledge=True, fail_web_search=True)
    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="How do I water my Pata?",
        plant_hint=None,
        plant_binomial_name=CONFIRMED_BINOMIAL,
    )

    assert tools.web_search_calls == 1
    assert "I did not find enough evidence" in result["answer"]
    assert "https://www.google.com/search?q=trusted" not in result["answer"]
    assert "trusted_web_search failed" in result["tool_failures"][0]
    assert "web_search_used" in result["fallback_reasons"]

async def test_assistant_records_ingestion_failure_without_blocking_web_answer() -> None:
    tools = FakeTools(
        degraded_knowledge=True,
        fail_ingestion=True,
        web_results=[
            SearchResult(
                title="Trusted watering guide",
                url="https://example.org/watering",
                snippet="Use a fast-draining substrate and water when the soil is dry.",
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

    assert tools.ingestion_calls == 0
    assert result["answer"] == "Synthesized model response."
    assert "Use a fast-draining substrate" in tools.model_prompts[0]
    assert result.get("tool_failures", []) == []
    assert result["ingestion_claims"]

async def test_assistant_service_saves_chat_after_fallback_persistence_failure(
    session_factory,
    monkeypatch: pytest.MonkeyPatch,
    ) -> None:
    class FakeGraph:
        async def run(
            self,
            *,
            user_id: UUID,
            message: str,
            plant_hint: str | None,
            plant_binomial_name: str | None = None,
            plant_scientific_name: str | None = None,
        ):
            return {
                "answer": "Synthesized model response.",
                "sources": [
                    {
                        "url": "https://example.org/watering",
                        "title": "Trusted watering guide",
                        "domain": "example.org",
                    }
                ],
                "tool_failures": ["ingest_web_evidence failed: pgvector unavailable"],
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
            payload=AssistantChatRequest(message="How do I water my Pata?", plant="Pata"),
        )

        messages = (await session.execute(select(conversation_messages))).all()

    assert response.message.content == "Synthesized model response."
    assert response.message.content_format == "plain_text"
    assert "pgvector unavailable" in response.tool_failures[0]
    assert [message.role for message in messages] == ["user", "assistant"]
    assert messages[1].metadata["content_format"] == "plain_text"
    assert messages[1].metadata["tool_failures"] == response.tool_failures

async def test_assistant_service_passes_taxonomy_context_to_graph(
    session_factory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class FakeGraph:
        async def run(self, **kwargs):
            captured.update(kwargs)
            return {"answer": "Synthesized model response.", "sources": [], "tool_failures": []}

    monkeypatch.setattr(
        "app.assistant.tools.facade.get_provider_registry",
        lambda: SimpleNamespace(search=object(), embeddings=object()),
    )
    async with session_factory() as session:
        service = AssistantService(session)
        service.graph = FakeGraph()
        await service.chat(
            user_id=uuid4(),
            payload=AssistantChatRequest(
                message="How do I water this plant?",
                plant="Tomato",
                plant_binomial_name="Solanum lycopersicum",
                plant_scientific_name="Solanum lycopersicum var. cerasiforme",
            ),
        )
        messages = (await session.execute(select(conversation_messages))).all()

    assert captured["plant_hint"] == "Tomato"
    assert captured["plant_binomial_name"] == "Solanum lycopersicum"
    assert captured["plant_scientific_name"] == "Solanum lycopersicum var. cerasiforme"
    assert messages[0].metadata["display_plant_name"] == "Tomato"
    assert messages[0].metadata["operational_plant_name"] == "Solanum lycopersicum"

async def test_assistant_service_does_not_mark_display_name_as_operational(
    session_factory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeGraph:
        async def run(self, **kwargs):
            return {"answer": "Synthesized model response.", "sources": [], "tool_failures": []}

    monkeypatch.setattr(
        "app.assistant.tools.facade.get_provider_registry",
        lambda: SimpleNamespace(search=object(), embeddings=object()),
    )
    async with session_factory() as session:
        service = AssistantService(session)
        service.graph = FakeGraph()
        await service.chat(
            user_id=uuid4(),
            payload=AssistantChatRequest(
                message="How do I water this plant?",
                plant="Tomato",
            ),
        )
        messages = (await session.execute(select(conversation_messages))).all()

    assert messages[0].metadata["display_plant_name"] == "Tomato"
    assert "operational_plant_name" not in messages[0].metadata

async def test_background_ingestion_failure_logs_plant_and_source_context(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def rollback(self) -> None:
            pass

        async def commit(self) -> None:
            pass

    class FailingTools:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def ingest_validated_claims(self, claims):
            return ToolResult(ok=False, error="embedding unavailable")

    claims = [
        {
            "scientific_name": "Cotyledon tomentosa",
            "source_url": "https://example.org/watering",
            "source_domain": "example.org",
        }
    ]
    monkeypatch.setattr(assistant_service, "AsyncSessionLocal", lambda: FakeSession())
    monkeypatch.setattr(assistant_service, "AssistantTools", FailingTools)
    caplog.set_level("WARNING", logger="app.assistant.service")

    await _ingest_validated_claims_background(
        claims=claims,
        conversation_id=uuid4(),
        answerability_status="partial",
    )

    record = next(
        item for item in caplog.records if item.message == "assistant_validated_claim_ingestion_failed"
    )
    assert record.answerability_status == "partial"
    assert record.claim_count == 1
    assert record.scientific_names == ["Cotyledon tomentosa"]
    assert record.source_urls == ["https://example.org/watering"]
    assert record.source_domains == ["example.org"]
    assert record.error == "embedding unavailable"

async def test_background_ingestion_exception_logs_plant_and_source_context(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def rollback(self) -> None:
            pass

        async def commit(self) -> None:
            pass

    class RaisingTools:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def ingest_validated_claims(self, claims):
            raise RuntimeError("index unavailable")

    claims = [
        {
            "scientific_name": "Cotyledon tomentosa",
            "source_url": "https://example.org/watering",
            "source_domain": "example.org",
        }
    ]
    monkeypatch.setattr(assistant_service, "AsyncSessionLocal", lambda: FakeSession())
    monkeypatch.setattr(assistant_service, "AssistantTools", RaisingTools)
    caplog.set_level("ERROR", logger="app.assistant.service")

    await _ingest_validated_claims_background(
        claims=claims,
        conversation_id=uuid4(),
        answerability_status="partial",
    )

    record = next(
        item for item in caplog.records if item.message == "assistant_validated_claim_ingestion_exception"
    )
    assert record.answerability_status == "partial"
    assert record.claim_count == 1
    assert record.scientific_names == ["Cotyledon tomentosa"]
    assert record.source_urls == ["https://example.org/watering"]
    assert record.source_domains == ["example.org"]

async def test_assistant_service_total_generation_failure_returns_retryable_error(
    session_factory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When graph returns total_generation_failure, service returns AssistantRetryableError
    with only the user message persisted and no assistant message."""

    class FakeGraph:
        async def run(self, **kwargs):
            from app.assistant.tools import AssistantFailureMetadata, ProviderFailureEntry
            return {
                "total_generation_failure": True,
                "tool_failures": ["all providers failed: gemini unavailable"],
                "generation_failure": AssistantFailureMetadata(
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
            payload=AssistantChatRequest(message="How do I water my Pata?", plant="Pata"),
        )

        messages = (await session.execute(select(conversation_messages))).all()

    from app.assistant.schemas import AssistantRetryableError
    assert isinstance(response, AssistantRetryableError)
    assert response.retryable is True
    assert response.failure_category == "all_providers_failed"
    assert response.provider_failures[0].failure_category == "service_unavailable"
    assert response.provider_failures[0].provider == "gemini"
    assert response.conversation_id is not None
    assert [message.role for message in messages] == ["user"]

