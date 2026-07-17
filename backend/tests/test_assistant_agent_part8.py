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
from tests._assistant_helpers import CHEMICAL_TREATMENT_CLASSIFIER
from tests._assistant_helpers import CONFIRMED_BINOMIAL
from tests._assistant_helpers import PESTICIDE_INSTRUCTION_CLASSIFIER
from tests._assistant_helpers import PEST_CLASSIFIER
from tests._assistant_helpers import SAFETY_BOUNDARY_CASES
from tests._assistant_helpers import SAFETY_PET_CLASSIFIER

async def test_web_search_timeout_returns_controlled_fallback() -> None:
    from app.core.settings import Settings
    tools = SlowWebSearchTools(rag_answerable=False)
    settings = Settings(assistant_web_search_timeout_seconds=0.1)
    result = await AssistantGraph(tools, settings=settings).run(
        user_id=uuid4(),
        message="How often should I water my Pata?",
        plant_hint=None,
        plant_binomial_name=CONFIRMED_BINOMIAL,
    )

    assert any("timed out" in f for f in result.get("tool_failures", []))


# --- Derived binomial operational name tests ---

def test_binomial_from_scientific_name_extracts_genus_species() -> None:
    assert _binomial_from_scientific_name("Epipremnum aureum (Linden & André) G.S.Bunting") == "Epipremnum aureum"

def test_binomial_from_scientific_name_extracts_infraspecific() -> None:
    assert _binomial_from_scientific_name("Solanum lycopersicum var. cerasiforme") == "Solanum lycopersicum"

def test_binomial_from_scientific_name_returns_none_for_single_token() -> None:
    assert _binomial_from_scientific_name("Epipremnum") is None

def test_binomial_from_scientific_name_returns_none_for_blank() -> None:
    assert _binomial_from_scientific_name("") is None
    assert _binomial_from_scientific_name(None) is None

def test_binomial_from_scientific_name_returns_none_for_non_latin_first_token() -> None:
    assert _binomial_from_scientific_name("Pata de oso") is None

def test_binomial_from_scientific_name_returns_none_for_single_char_token() -> None:
    assert _binomial_from_scientific_name("E. aureum") is None

def test_operational_plant_name_prefers_explicit_binomial() -> None:
    result = operational_plant_name(
        plant="Tomato",
        plant_binomial_name="Solanum lycopersicum",
        plant_scientific_name="Solanum lycopersicum var. cerasiforme",
    )
    assert result == "Solanum lycopersicum"

def test_operational_plant_name_derives_binomial_from_scientific() -> None:
    result = operational_plant_name(
        plant="Tomato",
        plant_binomial_name=None,
        plant_scientific_name="Solanum lycopersicum var. cerasiforme",
    )
    assert result == "Solanum lycopersicum"

def test_operational_plant_name_falls_back_to_normalized_scientific() -> None:
    result = operational_plant_name(
        plant="Pata",
        plant_binomial_name=None,
        plant_scientific_name="Pata de oso",
    )
    assert result == "Pata de oso"

def test_operational_plant_name_returns_none_for_blank_values() -> None:
    result = operational_plant_name(
        plant=None,
        plant_binomial_name=None,
        plant_scientific_name=None,
    )
    assert result is None

async def test_authority_scientific_name_derives_binomial_for_knowledge_search_and_web_query() -> None:
    tools = FakeTools(
        degraded_knowledge=True,
        plant_data=_structured_evidence(),
        web_results=[
            SearchResult(
                title="Trusted care guide",
                url="https://example.org/care",
                snippet="Water when the substrate dries.",
                source_domain="example.org",
            )
        ],
    )
    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="How do I water this plant?",
        plant_hint="Pothos",
        plant_scientific_name="Epipremnum aureum (Linden & André) G.S.Bunting",
    )

    assert result["answer"] == "Synthesized model response."
    assert tools.knowledge_search_kwargs["scientific_name"] == "Epipremnum aureum"
    assert "Epipremnum aureum" in tools.web_search_query
    assert "(Linden" not in tools.web_search_query

async def test_infraspecific_scientific_name_derives_species_binomial_for_retrieval() -> None:
    tools = FakeTools(
        degraded_knowledge=True,
        plant_data=_structured_evidence(),
        web_results=[
            SearchResult(
                title="Trusted care guide",
                url="https://example.org/care",
                snippet="Water when the substrate dries.",
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

async def test_explicit_binomial_wins_over_derived_binomial_from_scientific() -> None:
    tools = FakeTools(
        degraded_knowledge=True,
        plant_data=_structured_evidence(),
        web_results=[
            SearchResult(
                title="Trusted care guide",
                url="https://example.org/care",
                snippet="Water when the substrate dries.",
                source_domain="example.org",
            )
        ],
    )
    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="How do I water this plant?",
        plant_hint="Tomato",
        plant_binomial_name="Solanum lycopersicum",
        plant_scientific_name="Solanum lycopersicum var. cerasiforme",
    )

    assert result["answer"] == "Synthesized model response."
    assert tools.knowledge_search_kwargs["scientific_name"] == "Solanum lycopersicum"

async def test_blank_or_missing_taxonomy_preserves_existing_missing_taxonomy_behavior() -> None:
    tools = FakeTools()
    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="How do I water this plant?",
        plant_hint="Potus",
    )

    assert "confirmed scientific name" in result["answer"]
    assert tools.knowledge_search_kwargs is None
    assert tools.plant_data_calls == 0

# --- Expanded taxonomy regression tests ---

async def test_classifier_watering_returns_domain_qualified_aspect() -> None:
    tools = FakeTools()
    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="How often should I water my Pata?",
        plant_hint=None,
    )
    assert result["topic"] == "watering"
    assert "watering_frequency_or_trigger" in result["required_aspects"]

async def test_classifier_light_returns_domain_qualified_aspect() -> None:
    tools = FakeTools()
    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="How much light does my Pata need?",
        plant_hint=None,
    )
    assert result["topic"] == "light"
    assert "light_exposure" in result["required_aspects"]

async def test_classifier_toxicity_returns_toxicity_safety_topic() -> None:
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
        plant_binomial_name=CONFIRMED_BINOMIAL,
    )
    assert result["topic"] == "toxicity_safety"
    assert "toxicity_pet_safety" in result["required_aspects"]
    assert "pet_toxicity" not in result["required_aspects"]
