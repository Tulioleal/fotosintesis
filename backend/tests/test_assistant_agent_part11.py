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

async def test_disclaimed_guidance_emits_no_ingestion_claims() -> None:
    """4.3 - Insufficient disclaimed-guidance answers must not emit ingestion claims."""
    tools = FakeTools(
        rag_answerable=False,
        plant_data=None,
        web_results=[],
        classifier_data=PEST_CLASSIFIER,
        model_response=(
            "What the sources validated: none. "
            "What the sources did not validate: insect identification. "
            "General unvalidated guidance: inspect the underside. "
            "Details that would help: a close-up photo."
        ),
    )

    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="Veo unos insectos blancos pequenos debajo de las hojas",
        plant_hint=None,
        plant_binomial_name=CONFIRMED_BINOMIAL,
    )

    assert result["answerability_status"] == "insufficient"
    assert result.get("ingestion_claims", []) == []
    assert result.get("source_support", []) == []
    assert result["llm_general_guidance_used"] is True
    assert result["diagnostics"]["llm_general_guidance_used"] is True

async def test_partial_evidence_ingestion_uses_only_validated_source_support() -> None:
    """4.4 - Partial answers persist ingestion only from validated source_support, not general guidance."""
    partial_data = {
        "status": "partial",
        "covered_aspects": ["pest_identification"],
        "missing_aspects": ["pest_treatment_action"],
        "source_support": [
            {
                "claim": "Identificacion de la plaga validada por la ficha botanica.",
                "source_urls": ["https://example.org/pests"],
                "covered_aspects": ["pest_identification"],
                "evidence_quote": "Las cochinillas aparecen como pequenos insectos blancos.",
                "confidence": 0.88,
            }
        ],
        "contradictions": [],
        "confidence": 0.88,
        "score": 0.88,
        "passed": False,
        "reasons": ["treatment_action is not directly supported"],
    }

    class PartialDisclaimedJudgeTools(FakeTools):
        async def judge_response(self, payload: dict, rubric: dict, **kwargs) -> object:
            self.judge_calls.append({"payload": payload, "rubric": rubric})
            if payload.get("evidence_type") in {"rag", "combined_rag_web"}:
                return JudgeResult.from_provider_data(
                    provider="test-judge",
                    model="test-model",
                    passing_score=1.0,
                    data=partial_data,
                )
            return await super().judge_response(payload, rubric, **kwargs)

    tools = PartialDisclaimedJudgeTools(
        web_results=[
            SearchResult(
                title="Trusted pest identification guide",
                url="https://example.org/pests",
                snippet="Las cochinillas aparecen como pequenos insectos blancos.",
                source_domain="example.org",
            ),
            SearchResult(
                title="Trusted pest treatment guide",
                url="https://example.org/pests-treatment",
                snippet="Para tratar cochinillas, aislar la planta y limpiar con un pano humedo.",
                source_domain="example.org",
            ),
        ],
        classifier_data={
            "language": "en",
            "answer_language": "en",
            "intent": "plant_care_question",
            "topic": "pests",
            "required_aspects": ["pest_identification", "pest_treatment_action"],
            "plant_reference": "Pata",
            "confidence": 0.9,
            "needs_retrieval": True,
        },
    )

    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="Que insecto es este y como lo trato?",
        plant_hint=None,
        plant_binomial_name=CONFIRMED_BINOMIAL,
    )

    assert result["answerability_status"] == "partial"
    assert result["covered_aspects"] == ["pest_identification"]
    assert result["missing_aspects"] == ["pest_treatment_action"]
    assert result.get("llm_general_guidance_used") is not True
    ingestion_claims = result.get("ingestion_claims", [])
    assert len(ingestion_claims) == 1
    claim = ingestion_claims[0]
    assert claim["covered_aspects"] == ["pest_identification"]
    assert claim["source_url"] == "https://example.org/pests"
    assert "pest_treatment_action" not in claim["covered_aspects"]

async def test_safety_sensitive_missing_aspect_keeps_conservative_fallback() -> None:
    """4.5 - Unsupported safety-sensitive claims stay on the conservative fallback path."""
    tools = FakeTools(
        rag_answerable=False,
        plant_data=None,
        web_results=[],
        classifier_data=SAFETY_PET_CLASSIFIER,
    )

    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="Is my Pata safe for pets?",
        plant_hint=None,
        plant_binomial_name=CONFIRMED_BINOMIAL,
    )

    assert result.get("llm_general_guidance_used") is not True
    assert "conservative_safety_fallback" in result["fallback_reasons"]
    assert "I did not find direct and reliable evidence" in result["answer"]
    assert "out of reach of pets" in result["answer"]
    assert result["diagnostics"]["llm_general_guidance_used"] is False

async def test_multilingual_pest_question_routes_by_schema_state_not_keywords() -> None:
    """4.6 - Multilingual paraphrased pest question uses schema-validated state, not keywords."""
    tools = FakeTools(
        rag_answerable=False,
        plant_data=None,
        web_results=[],
        classifier_data={
            "language": "it",
            "answer_language": "it",
            "intent": "plant_care_question",
            "topic": "pests",
            "required_aspects": ["pest_identification", "pest_isolation_steps"],
            "plant_reference": "Pata",
            "confidence": 0.9,
            "needs_retrieval": True,
        },
        model_response=(
            "Cosa hanno convalidato le fonti: nulla. "
            "Cosa non hanno convalidato le fonti: identificazione dell'insetto. "
            "Orientamento generale non convalidato: ispezionare la pagina inferiore delle foglie. "
            "Dettagli che aiuterebbero: una foto ravvicinata dell'insetto."
        ),
    )

    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="Vedo dei piccoli insetti bianchi sotto le foglie della mia Pata",
        plant_hint=None,
        plant_binomial_name=CONFIRMED_BINOMIAL,
    )

    assert result["sufficient"] is False
    assert result["answerability_status"] == "insufficient"
    assert result["llm_general_guidance_used"] is True
    assert result["diagnostics"]["answer_language"] == "it"
    assert result["diagnostics"]["llm_general_guidance_used"] is True
    assert result["diagnostics"]["missing_aspects"] == ["pest_identification", "pest_isolation_steps"]

    disclaimed_prompts = [
        p for p in tools.model_prompts
        if "What the sources validated" in p and "General unvalidated guidance" in p
    ]
    assert len(disclaimed_prompts) >= 1
    assert "answer_language (it)" in disclaimed_prompts[0]
    assert "Vedo dei piccoli insetti bianchi" in disclaimed_prompts[0]


# ---------------------------------------------------------------------------
# Combined RAG+web insufficient-evidence coverage
# ---------------------------------------------------------------------------

async def test_combined_rag_web_insufficient_routes_to_disclaimed_guidance() -> None:
    """RAG insufficient + web insufficient (combined judge) -> disclaimed guidance, no ingestion."""
    insufficient_combined_data = {
        "status": "insufficient",
        "covered_aspects": [],
        "missing_aspects": [
            "pest_identification",
            "pest_isolation_steps",
            "pest_prevention_steps",
        ],
        "source_support": [],
        "contradictions": [],
        "confidence": 0.32,
        "score": 0.32,
        "passed": False,
        "reasons": ["combined RAG+web evidence does not directly answer pest identification"],
    }

    class CombinedInsufficientJudgeTools(FakeTools):
        async def judge_response(self, payload: dict, rubric: dict, **kwargs) -> object:
            self.judge_calls.append({"payload": payload, "rubric": rubric})
            if payload.get("evidence_type") in {"rag", "combined_rag_web"}:
                return JudgeResult.from_provider_data(
                    provider="test-judge",
                    model="test-model",
                    passing_score=1.0,
                    data=insufficient_combined_data,
                )
            return await super().judge_response(payload, rubric, **kwargs)

    tools = CombinedInsufficientJudgeTools(
        web_results=[
            SearchResult(
                title="Generic plant care article",
                url="https://example.org/care",
                snippet="This plant prefers bright light and well-drained soil.",
                source_domain="example.org",
            ),
            SearchResult(
                title="Vague pest overview",
                url="https://example.org/pests",
                snippet="Many houseplants can be affected by common pests; consult a local expert.",
                source_domain="example.org",
            ),
        ],
        classifier_data=PEST_CLASSIFIER,
        model_response=(
            "What the sources validated: no part was validated. "
            "What the sources did not validate: insect identification, "
            "isolation and prevention steps. "
            "General unvalidated guidance: check the underside of the leaves, "
            "isolate the plant and manually remove with water or a damp cloth. "
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
    assert result.get("ingestion_claims", []) == []
    assert result.get("source_support", []) == []

    assert "What the sources validated" in result["answer"]
    assert "General unvalidated guidance" in result["answer"]
    assert "Details that would help" in result["answer"]

    assert "No direct evidence" not in result["answer"]
    assert "conservative_safety_fallback" not in result["fallback_reasons"]

    diagnostics = result["diagnostics"]
    assert diagnostics["llm_general_guidance_used"] is True
    assert diagnostics["missing_aspects"] == [
        "pest_identification",
        "pest_isolation_steps",
        "pest_prevention_steps",
    ]
    assert diagnostics["covered_aspects"] == []
    assert diagnostics["answerability_status"] == "insufficient"

    combined_judge_calls = [
        c for c in tools.judge_calls
        if c["payload"].get("evidence_type") == "combined_rag_web"
    ]
    assert len(combined_judge_calls) >= 1

    disclaimed_prompts = [
        p for p in tools.model_prompts
        if "What the sources validated" in p and "General unvalidated guidance" in p
    ]
    assert len(disclaimed_prompts) >= 1
    assert "do not cite any source" in disclaimed_prompts[0]
    assert "https://example.org/care" not in disclaimed_prompts[0]
    assert "https://example.org/pests" not in disclaimed_prompts[0]


# ---------------------------------------------------------------------------
# Broader safety-boundary coverage
# ---------------------------------------------------------------------------


CHEMICAL_TREATMENT_CLASSIFIER = {
    "language": "en",
    "answer_language": "en",
    "intent": "plant_care_question",
    "topic": "pests",
    "required_aspects": [
        "safety_chemical_treatment_precautions",
        "pest_treatment_action",
    ],
    "plant_reference": "Pata",
    "confidence": 0.9,
    "needs_retrieval": True,
}


PESTICIDE_INSTRUCTION_CLASSIFIER = {
    "language": "en",
    "answer_language": "en",
    "intent": "plant_care_question",
    "topic": "pests",
    "required_aspects": [
        "safety_chemical_treatment_precautions",
        "pest_treatment_action",
    ],
    "plant_reference": "Pata",
    "confidence": 0.88,
    "needs_retrieval": True,
}


SAFETY_BOUNDARY_CASES = [
    pytest.param(
        SAFETY_PET_CLASSIFIER,
        "Es toxica para gatos mi Pata?",
        id="pet_safety",
    ),
    pytest.param(
        CHEMICAL_TREATMENT_CLASSIFIER,
        "Que precauciones debo tomar al aplicar un tratamiento quimico a mi Pata?",
        id="chemical_treatment_precautions",
    ),
    pytest.param(
        {
            "language": "es",
            "answer_language": "es",
            "intent": "plant_care_question",
            "topic": "pests",
            "required_aspects": [
                "safety_disposal_precautions",
                "pest_treatment_action",
            ],
            "plant_reference": "Pata",
            "confidence": 0.9,
            "needs_retrieval": True,
        },
        "Como desecho de forma segura los residuos del tratamiento de mi Pata?",
        id="safety_disposal_precautions",
    ),
]

async def test_pesticide_instruction_request_does_not_return_chemical_advice() -> None:
    """Insecticide / pesticide instructions without source support stay on the conservative path."""
    tools = FakeTools(
        rag_answerable=False,
        plant_data=None,
        web_results=[],
        classifier_data=PESTICIDE_INSTRUCTION_CLASSIFIER,
    )

    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="What insecticide or pesticide should I apply to my Pata and at what dose?",
        plant_hint=None,
        plant_binomial_name=CONFIRMED_BINOMIAL,
    )

    assert result.get("llm_general_guidance_used") is not True
    assert result.get("ingestion_claims", []) == []
    assert result.get("source_support", []) == []
    assert "conservative_safety_fallback" in result["fallback_reasons"]

    disclaimed_prompts = [
        p for p in tools.model_prompts
        if "What the sources validated" in p and "General unvalidated guidance" in p
    ]
    assert disclaimed_prompts == []

    answer_text = (result.get("answer") or "").casefold()
    for forbidden in (
        "imidacloprid",
        "malathion",
        "pyrethrin",
        "neem",
        "neem oil",
        "1 ml",
        "2 ml",
        "5 ml",
        "10 ml",
        "grams per liter",
        "recommended dose",
        "apply every",
    ):
        assert forbidden not in answer_text

    assert result["diagnostics"]["llm_general_guidance_used"] is False


# =============================================================================
# Grounded answer prompt tests - no attribution in prose
# =============================================================================

def test_grounded_prompt_prohibits_urls_and_source_labels() -> None:
    """Prompt builder must prohibit URLs, institution names, and source-label blocks."""
    from app.assistant.graph import _grounded_answer_prompt

    prompt = _grounded_answer_prompt(
        user_message="How do I care for my Neon Pothos?",
        plant_name="Neon Pothos",
        topic="care_instructions",
        evidence_type="web_rag",
        evidence="Neon Pothos thrives in medium to low light.",
        limitations=[],
        source_metadata=[{"url": "https://extension.illinois.edu/houseplants", "title": "Illinois Extension"}],
        extra_context="",
        answer_language="es",
        required_aspects=["light_exposure", "watering_frequency_or_trigger"],
        covered_aspects=["light_exposure"],
        missing_aspects=["watering_frequency_or_trigger"],
        answerability_status="partial",
        source_support=[
            {
                "claim": "Neon Pothos thrives in medium to low light.",
                "source_urls": ["https://extension.illinois.edu/houseplants"],
                "covered_aspects": ["light_exposure"],
                "evidence_quote": " prosp...",
                "confidence": 0.85,
            }
        ],
        contradictions=[],
    )

    assert "DO NOT MENTION URLs" in prompt
    assert "names of institutions" in prompt
    assert "'Source-backed'" in prompt
    assert "answer_language (es)" in prompt
    assert "toxicity" in prompt
    assert "edibility" in prompt
    assert "insecticide" in prompt
    # The connector guidance must be language-aware: the prompt must ask for a
    # language-appropriate discourse marker and forbid mixing languages, while
    # NOT prescribing a fixed list of English connectors as the only option.
    assert "language-appropriate discourse marker" in prompt
    assert "Do not mix languages" in prompt
    forbidden_literals = (
        "'As a general guideline…', 'In general terms…', "
        "'A common complementary practice is…', 'As a complementary reference…'"
    )
    assert forbidden_literals not in prompt
    assert "one of these connectors" not in prompt

def test_grounded_prompt_prohibits_urls_and_source_labels_english() -> None:
    """Prompt builder must preserve non-default answer_language."""
    from app.assistant.graph import _grounded_answer_prompt

    prompt = _grounded_answer_prompt(
        user_message="How do I care for my Neon Pothos?",
        plant_name="Neon Pothos",
        topic="care_instructions",
        evidence_type="web_rag",
        evidence="Neon Pothos thrives in medium to low light.",
        limitations=[],
        source_metadata=[{"url": "https://extension.illinois.edu/houseplants", "title": "Illinois Extension"}],
        extra_context="",
        answer_language="en",
        required_aspects=["light_exposure"],
        covered_aspects=["light_exposure"],
        missing_aspects=[],
        answerability_status="full",
        source_support=[
            {
                "claim": "Neon Pothos thrives in medium to low light.",
                "source_urls": ["https://extension.illinois.edu/houseplants"],
                "covered_aspects": ["light_exposure"],
                "evidence_quote": "...",
                "confidence": 0.85,
            }
        ],
        contradictions=[],
    )

    assert "answer_language (en)" in prompt
    # The same language-aware connector guidance must apply regardless of the
    # target language: it asks for a discourse marker in the response language
    # and never imposes a fixed English-only list.
    assert "language-appropriate discourse marker" in prompt
    assert "Do not mix languages" in prompt
    forbidden_literals = (
        "'As a general guideline…', 'In general terms…', "
        "'A common complementary practice is…', 'As a complementary reference…'"
    )
    assert forbidden_literals not in prompt
    assert "one of these connectors" not in prompt

async def test_grounded_prompt_does_not_impose_english_connector_list_when_es() -> None:
    """The grounded prompt used at runtime for answer_language=es must not
    prescribe a fixed English connector list and must ask for a
    language-appropriate discourse marker instead.
    """
    tools = FakeTools(
        rag_answerable=True,
        plant_data=None,
        web_results=[],
        classifier_data={
            "language": "es",
            "answer_language": "es",
            "intent": "plant_care_question",
            "topic": "watering",
            "required_aspects": ["watering_frequency_or_trigger"],
            "plant_reference": "Pata",
            "confidence": 0.9,
            "needs_retrieval": True,
        },
        model_response=(
            "Tu Pata necesita riego cuando los primeros 2-3 cm de sustrato estén secos. "
            "Como pauta general, evita encharcamientos y deja escurrir el agua sobrante."
        ),
    )

    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="Cada cuánto riego mi Pata?",
        plant_hint=None,
        plant_binomial_name="Epipremnum aureum",
    )

    assert result["answer"] is not None
    grounded_prompts = [
        p for p in tools.model_prompts
        if "Respond in the language indicated by answer_language" in p
    ]
    assert grounded_prompts, "expected at least one grounded prompt to be captured"
    prompt = grounded_prompts[-1]
    assert "answer_language (es)" in prompt
    assert "language-appropriate discourse marker" in prompt
    assert "Do not mix languages" in prompt
    forbidden_literals = (
        "'As a general guideline…', 'In general terms…', "
        "'A common complementary practice is…', 'As a complementary reference…'"
    )
    assert forbidden_literals not in prompt
    assert "one of these connectors" not in prompt

async def test_grounded_prompt_does_not_impose_english_connector_list_when_it() -> None:
    """The grounded prompt used at runtime for answer_language=it must not
    prescribe a fixed English connector list and must ask for a
    language-appropriate discourse marker instead.
    """
    tools = FakeTools(
        rag_answerable=True,
        plant_data=None,
        web_results=[],
        classifier_data={
            "language": "it",
            "answer_language": "it",
            "intent": "plant_care_question",
            "topic": "watering",
            "required_aspects": ["watering_frequency_or_trigger"],
            "plant_reference": "Pata",
            "confidence": 0.9,
            "needs_retrieval": True,
        },
        model_response=(
            "La tua Pata va annaffiata quando i primi 2-3 cm di substrato sono asciutti. "
            "Come linea guida generale, evita i ristagni e lascia scolare l'acqua in eccesso."
        ),
    )

    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="Ogni quanto devo annaffiare la mia Pata?",
        plant_hint=None,
        plant_binomial_name="Epipremnum aureum",
    )

    assert result["answer"] is not None
    grounded_prompts = [
        p for p in tools.model_prompts
        if "Respond in the language indicated by answer_language" in p
    ]
    assert grounded_prompts, "expected at least one grounded prompt to be captured"
    prompt = grounded_prompts[-1]
    assert "answer_language (it)" in prompt
    assert "language-appropriate discourse marker" in prompt
    assert "Do not mix languages" in prompt
    forbidden_literals = (
        "'As a general guideline…', 'In general terms…', "
        "'A common complementary practice is…', 'As a complementary reference…'"
    )
    assert forbidden_literals not in prompt
    assert "one of these connectors" not in prompt

def test_grounded_prompt_structured_api_no_attribution_instruction() -> None:
    """For structured_api evidence type, attribution_instruction must NOT appear."""
    from app.assistant.graph import _grounded_answer_prompt

    prompt = _grounded_answer_prompt(
        user_message="How do I care for my plant?",
        plant_name="Planta",
        topic="care_instructions",
        evidence_type="structured_api",
        evidence="The plant requires moderate watering.",
        limitations=[],
        source_metadata=[{"url": "https://example.org", "title": "Example"}],
        extra_context="",
        answer_language="es",
        required_aspects=["watering_frequency_or_trigger"],
        covered_aspects=["watering_frequency_or_trigger"],
        missing_aspects=[],
        answerability_status="full",
        source_support=[
            {
                "claim": "The plant requires moderate watering.",
                "source_urls": ["https://example.org"],
                "covered_aspects": ["watering_frequency_or_trigger"],
                "evidence_quote": "...",
                "confidence": 0.85,
            }
        ],
        contradictions=[],
    )

    assert "structured provider sources" not in prompt
    assert "Evidence type: structured_api" in prompt


# =============================================================================
# Grounded answer end-to-end tests - response must not leak sources
# =============================================================================

async def test_grounded_response_does_not_leak_sources_to_text() -> None:
    """Response content must not contain URLs or Source-backed labels even if model emits them."""
    tools = FakeTools(
        rag_answerable=True,
        plant_data=None,
        web_results=[],
        classifier_data={
            "language": "en",
            "answer_language": "en",
            "intent": "plant_care_question",
            "topic": "light",
            "required_aspects": ["light_exposure"],
            "plant_reference": "Neon Pothos",
            "confidence": 0.92,
            "needs_retrieval": True,
        },
        model_response="For your Neon Pothos to thrive, give it medium to low light. Source-backed: https://extension.illinois.edu/houseplants/varieties?utm_source=openai",
    )

    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="How much light does my Neon Pothos need?",
        plant_hint=None,
        plant_binomial_name="Epipremnum aureum",
    )

    assert "http" not in result["answer"]
    assert "Source-backed:" not in result["answer"]
    assert "extension.illinois.edu" not in result["answer"]

async def test_grounded_response_single_url_leak_to_prose() -> None:
    """When model emits a single URL in prose, it must not reach message.content."""
    tools = FakeTools(
        rag_answerable=True,
        plant_data=None,
        web_results=[],
        classifier_data={
            "language": "en",
            "answer_language": "en",
            "intent": "plant_care_question",
            "topic": "light",
            "required_aspects": ["light_exposure"],
            "plant_reference": "Neon Pothos",
            "confidence": 0.92,
            "needs_retrieval": True,
        },
        model_response="Your Neon Pothos prefers medium to low light. Source: https://extension.illinois.edu/houseplants",
    )

    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="How much light does my Neon Pothos need?",
        plant_hint=None,
        plant_binomial_name="Epipremnum aureum",
    )

    assert "http" not in result["answer"]
    assert "extension.illinois.edu" not in result["answer"]

async def test_grounded_response_multiple_urls_leak_to_prose() -> None:
    """When model emits two URLs in prose, neither must reach message.content."""
    tools = FakeTools(
        rag_answerable=True,
        plant_data=None,
        web_results=[],
        classifier_data={
            "language": "en",
            "answer_language": "en",
            "intent": "plant_care_question",
            "topic": "care_general",
            "required_aspects": ["watering_frequency_or_trigger", "light_exposure"],
            "plant_reference": "Pothos",
            "confidence": 0.92,
            "needs_retrieval": True,
        },
        model_response="Your plant needs medium light and water when the soil is dry. Source 1: https://example.com/light. Source 2: https://example.com/water",
    )

    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="How do I care for my plant?",
        plant_hint=None,
        plant_binomial_name="Epipremnum aureum",
    )

    assert "http" not in result["answer"]
    assert "example.com" not in result["answer"]

async def test_grounded_response_partial_with_general_guidance_connector() -> None:
    """Partial answer must include a soft connector for general guidance."""
    tools = FakeTools(
        rag_answerable=True,
        plant_data=None,
        web_results=[],
        classifier_data={
            "language": "en",
            "answer_language": "en",
            "intent": "plant_care_question",
            "topic": "care_general",
            "required_aspects": ["watering_frequency_or_trigger", "light_exposure"],
            "plant_reference": "Pothos",
            "confidence": 0.92,
            "needs_retrieval": True,
        },
        model_response="Your Pothos can live with medium light. As a general guideline, water when the soil is dry.",
    )

    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="How do I care for my Pothos?",
        plant_hint=None,
        plant_binomial_name="Epipremnum aureum",
    )

    content = result["answer"]
    assert "As a general guideline" in content
    assert "http" not in content
    assert "Source-backed:" not in content

async def test_grounded_response_contradictory_generic_phrasing() -> None:
    """Contradictory evidence must use generic phrasing without source names."""
    tools = FakeTools(
        rag_answerable=True,
        plant_data=None,
        web_results=[],
        classifier_data={
            "language": "en",
            "answer_language": "en",
            "intent": "plant_care_question",
            "topic": "watering",
            "required_aspects": ["watering_frequency_or_trigger"],
            "plant_reference": "Pothos",
            "confidence": 0.92,
            "needs_retrieval": True,
        },
        model_response="There is contradictory information among the consulted sources about how often to water your plant. A general conservative measure is to check the soil before watering.",
    )

    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="How often should I water my Pothos?",
        plant_hint=None,
        plant_binomial_name="Epipremnum aureum",
    )

    content = result["answer"]
    assert "there is contradictory information" in content.lower() or "contradictory information" in content.lower()
    assert "http" not in content
    assert "extension.illinois.edu" not in content

async def test_grounded_response_institution_name_not_leaked() -> None:
    """Institution names emitted by the model must not reach result['answer']."""
    tools = FakeTools(
        rag_answerable=True,
        plant_data=None,
        web_results=[],
        classifier_data={
            "language": "en",
            "answer_language": "en",
            "intent": "plant_care_question",
            "topic": "light",
            "required_aspects": ["light_exposure"],
            "plant_reference": "Neon Pothos",
            "confidence": 0.92,
            "needs_retrieval": True,
        },
        model_response="According to Illinois Extension, your Neon Pothos prefers medium to low light.",
    )

    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="How much light does my Neon Pothos need?",
        plant_hint=None,
        plant_binomial_name="Epipremnum aureum",
    )

    assert "Illinois Extension" not in result["answer"]
    assert "http" not in result["answer"]

def test_grounded_answer_prompt_uses_display_name_in_prose() -> None:
    """Prompt builder must instruct the model to use the display name (nickname) in response prose."""
    from app.assistant.graph import _grounded_answer_prompt

    prompt = _grounded_answer_prompt(
        user_message="How do I water my Pata?",
        plant_name="Pata",
        topic="watering",
        evidence_type="rag",
        evidence="Moderate watering.",
        limitations=[],
        source_metadata=[{"url": "https://example.org", "title": "Example"}],
        extra_context="",
        answer_language="es",
    )

    assert "Selected plant: Pata" in prompt
    assert "When addressing the plant in the response" in prompt
    assert "always use the name provided as 'Selected plant'" in prompt
    assert "Never replace that name with the common name" in prompt
    assert "scientific name" in prompt
    assert "binomial" in prompt

def test_general_guidance_prompt_uses_display_name_in_prose() -> None:
    """Prompt builder must instruct the model to use the display name (nickname) in all four sections."""
    from app.assistant.graph import _general_guidance_with_disclaimer_prompt

    prompt = _general_guidance_with_disclaimer_prompt(
        user_message="What basic care does my Pata need?",
        plant_name="Pata",
        topic="care_instructions",
        answer_language="es",
        required_aspects=["watering", "light"],
        covered_aspects=[],
        missing_aspects=["watering", "light"],
        source_support=[],
        source_metadata=[],
    )

    assert "Selected plant: Pata" in prompt
    assert "When addressing the plant in the response" in prompt
    assert "always use the name provided as 'Selected plant'" in prompt
    assert "Never replace that name with the common name" in prompt
    assert "scientific name" in prompt
    assert "binomial" in prompt
    assert "all four sections" in prompt.lower()

def test_conservative_safety_fallback_includes_display_name_instruction() -> None:
    """Conservative safety fallback must include the display-name instruction in all three variants."""
    from app.assistant.graph import _conservative_safety_draft

    state_pet = {
        "message": "Is it safe for pets?",
        "display_plant_name": "Pata",
        "plant_binomial_name": "Cotyledon tomentosa",
        "plant_scientific_name": "Cotyledon tomentosa",
        "answer_language": "en",
    }
    state_edible = {
        "message": "Is it edible?",
        "display_plant_name": "Pata",
        "plant_binomial_name": "Cotyledon tomentosa",
        "plant_scientific_name": "Cotyledon tomentosa",
        "answer_language": "en",
    }
    state_generic = {
        "message": "What care do I need?",
        "display_plant_name": "Pata",
        "plant_binomial_name": "Cotyledon tomentosa",
        "plant_scientific_name": "Cotyledon tomentosa",
        "answer_language": "en",
    }

    draft_pet = _conservative_safety_draft(state_pet)
    draft_edible = _conservative_safety_draft(state_edible)
    draft_generic = _conservative_safety_draft(state_generic)

    pet_instruction = "When addressing the plant, use the name provided as 'Plant reference'"
    edible_instruction = "When addressing the plant, use the name provided as 'Plant reference'"
    generic_instruction = "When addressing the plant, use the name provided as 'Plant reference'"

    assert pet_instruction in str(draft_pet.required_points)
    assert edible_instruction in str(draft_edible.required_points)
    assert generic_instruction in str(draft_generic.required_points)

def test_simple_fallback_draft_includes_display_name_instruction_by_default() -> None:
    """Simple fallback draft must include the display-name instruction when no explicit required_points are passed."""
    from app.assistant.graph import _simple_fallback_draft

    state = {
        "message": "Does my plant need water?",
        "display_plant_name": "Pata",
        "plant_binomial_name": "Epipremnum aureum",
        "plant_scientific_name": "Epipremnum aureum",
        "answer_language": "en",
    }

    draft = _simple_fallback_draft(state, intent="test_intent")

    instruction = "When addressing the plant, use the name provided as 'Plant reference'"
    assert instruction in str(draft.required_points)
    assert "Pata" in str(draft.required_points)

def test_recovery_draft_includes_display_name_instruction() -> None:
    """Recovery draft must include the display-name instruction."""
    from app.assistant.graph import _recovery_draft_for_answer_generation

    state = {
        "message": "Does my Pata need light?",
        "display_plant_name": "Pata",
        "plant_binomial_name": "Epipremnum aureum",
        "plant_scientific_name": "Epipremnum aureum",
        "answer_language": "en",
    }

    draft = _recovery_draft_for_answer_generation(
        state,
        intent="recovery_test",
        evidence_type="rag",
        evidence="Some evidence",
        limitations=[],
        source_metadata=[],
    )

    instruction = "When addressing the plant, use the name provided as 'Plant reference'"
    assert instruction in str(draft.required_points)
    assert "Pata" in str(draft.required_points)

