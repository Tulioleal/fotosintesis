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

async def test_low_confidence_valid_classifier_preserves_answer_language() -> None:
    tools = FakeTools(
        classifier_data={
            "language": "en",
            "answer_language": "en",
            "intent": "out_of_domain",
            "topic": "unknown",
            "required_aspects": [],
            "plant_reference": None,
            "confidence": 0.2,
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
    assert not any("confidence" in f for f in result["tool_failures"])

async def test_invalid_classifier_output_falls_back_to_minimal_routing() -> None:
    tools = FakeTools(
        classifier_data={
            "language": "en",
            "answer_language": "en",
            "intent": "not_allowed",
            "topic": "watering",
            "required_aspects": ["watering_frequency_or_trigger"],
            "confidence": 0.95,
            "needs_retrieval": True,
        }
    )

    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="How often should I water my Pata?",
        plant_hint=None,
    )

    assert result["intent"] == "botanical"
    assert result["required_aspects"] == ["general_care_summary"]
    assert result["topic"] == "general_care"
    assert any("llm_classifier_invalid_output" in f for f in result["tool_failures"])

async def test_classifier_extra_fields_fall_back_to_minimal_routing() -> None:
    tools = FakeTools(
        classifier_data={
            "language": "en",
            "answer_language": "en",
            "intent": "not_allowed",
            "topic": "watering",
            "required_aspects": ["watering_frequency_or_trigger"],
            "plant_reference": "Pata",
            "confidence": 0.95,
            "needs_retrieval": True,
        }
    )

    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="How often should I water my Pata?",
        plant_hint=None,
        plant_binomial_name=CONFIRMED_BINOMIAL,
    )

    assert result["intent"] == "botanical"
    assert result["required_aspects"] == ["general_care_summary"]
    assert result["topic"] == "general_care"
    assert any("llm_classifier_invalid_output" in f for f in result["tool_failures"])

async def test_classifier_garden_action_does_not_run_care_evidence_operations() -> None:
    tools = FakeTools(
        classifier_data={
            "language": "en",
            "answer_language": "en",
            "intent": "garden_action",
            "topic": "unknown",
            "required_aspects": [],
            "plant_reference": "Pata",
            "confidence": 0.95,
            "needs_retrieval": False,
        }
    )

    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="Agrega mi Pata al jardin",
        plant_hint="Pata",
        plant_binomial_name=CONFIRMED_BINOMIAL,
    )

    assert result["intent"] == "out_of_domain"
    assert tools.knowledge_search_kwargs is None
    assert tools.plant_data_calls == 0
    assert tools.web_search_calls == 0
    assert "I can help with plant care" in result["answer"]

async def test_classifier_identification_question_does_not_run_care_evidence_operations() -> None:
    tools = FakeTools(
        classifier_data={
            "language": "en",
            "answer_language": "en",
            "intent": "plant_identification_question",
            "topic": "unknown",
            "required_aspects": [],
            "plant_reference": "Pata",
            "confidence": 0.95,
            "needs_retrieval": False,
        }
    )

    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="Identifica esta planta",
        plant_hint="Pata",
        plant_binomial_name=CONFIRMED_BINOMIAL,
    )

    assert result["intent"] == "out_of_domain"
    assert tools.knowledge_search_kwargs is None
    assert tools.plant_data_calls == 0
    assert tools.web_search_calls == 0
    assert "I can help with plant care" in result["answer"]

async def test_classifier_light_measurement_question_skips_care_retrieval() -> None:
    tools = FakeTools(
        classifier_data={
            "language": "en",
            "answer_language": "en",
            "intent": "light_measurement_question",
            "topic": "unknown",
            "required_aspects": [],
            "plant_reference": "Pata",
            "confidence": 0.95,
            "needs_retrieval": False,
        }
    )

    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="How do I measure the light for my Pata?",
        plant_hint="Pata",
        plant_binomial_name=CONFIRMED_BINOMIAL,
    )

    assert result["intent"] == "light"
    assert tools.knowledge_search_kwargs is None
    assert tools.plant_data_calls == 0
    assert tools.web_search_calls == 0

async def test_classifier_timeout_falls_back_to_minimal_routing() -> None:
    class TimeoutTools(FakeTools):
        async def generate_json(self, prompt: str, schema: dict, **kwargs) -> ToolResult:
            raise TimeoutError("classifier timeout")

    result = await AssistantGraph(TimeoutTools()).run(
        user_id=uuid4(),
        message="How often should I water my Pata?",
        plant_hint=None,
    )

    assert result["intent"] == "botanical"
    assert result["required_aspects"] == ["general_care_summary"]
    assert result["topic"] == "general_care"
    assert any("llm_classifier_timeout" in f for f in result["tool_failures"])

async def test_missing_confidence_repaired_by_retry_uses_llm_classification() -> None:
    class RetryTools(FakeTools):
        def __init__(self) -> None:
            super().__init__()
            self._classifier_call_count = 0

        async def generate_json(self, prompt: str, schema: dict, **kwargs) -> ToolResult:
            if self._classifier_call_count == 0:
                self._classifier_call_count += 1
                return ToolResult(
                    ok=True,
                    data={
                        "language": "en",
                        "answer_language": "en",
                        "intent": "plant_care_question",
                        "topic": "watering",
                        "required_aspects": ["watering_frequency_or_trigger"],
                        "plant_reference": "Pata",
                        "needs_retrieval": True,
                    },
                )
            return await super().generate_json(prompt, schema, **kwargs)

    tools = RetryTools()
    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="How often should I water my Pata?",
        plant_hint=None,
    )

    assert result["intent"] == "botanical"
    assert result["required_aspects"] == ["watering_frequency_or_trigger"]
    assert not result["tool_failures"] or not any(
        "invalid output" in f for f in result["tool_failures"]
    )

async def test_invalid_classifier_output_after_retry_falls_back_to_minimal_routing() -> None:
    class AlwaysInvalidTools(FakeTools):
        async def generate_json(self, prompt: str, schema: dict, **kwargs) -> ToolResult:
            return ToolResult(
                ok=True,
                data={
                    "language": "en",
                    "answer_language": "en",
                    "intent": "not_a_valid_intent",
                    "topic": "watering",
                    "required_aspects": ["watering_frequency_or_trigger"],
                    "confidence": 0.95,
                    "needs_retrieval": True,
                },
            )

    result = await AssistantGraph(AlwaysInvalidTools()).run(
        user_id=uuid4(),
        message="How often should I water my Pata?",
        plant_hint=None,
    )

    assert result["intent"] == "botanical"
    assert result["required_aspects"] == ["general_care_summary"]
    assert result["topic"] == "general_care"
    assert any("llm_classifier_invalid_output" in f for f in result["tool_failures"])

def test_classifier_schema_requires_confidence_and_care_classification_fields() -> None:
    required = CARE_CLASSIFIER_SCHEMA.get("required", [])
    assert "confidence" in required
    assert "language" in required
    assert "answer_language" in required
    assert "intent" in required
    assert "topic" in required
    assert "required_aspects" in required
    assert "plant_reference" in required
    assert "needs_retrieval" in required

async def test_missing_intent_repaired_by_retry_uses_llm_classification() -> None:
    """Regression: when the first classifier response omits a required field
    such as `intent`, the repair retry must succeed and the assistant MUST
    use the LLM classifier output for routing rather than fall back to minimal
    deterministic routing."""

    class _MissingIntentRetryTools(FakeTools):
        def __init__(self) -> None:
            super().__init__()
            self._classifier_call_count = 0
            self.repair_prompts: list[str] = []

        async def generate_json(self, prompt: str, schema: dict, **kwargs) -> ToolResult:
            self._classifier_call_count += 1
            if self._classifier_call_count == 1:
                self.repair_prompts.append(prompt)
                return ToolResult(
                    ok=True,
                    data={
                        "language": "en",
                        "answer_language": "en",
                        "topic": "watering",
                        "required_aspects": ["watering_frequency_or_trigger"],
                        "plant_reference": "Pata",
                        "confidence": 0.9,
                        "needs_retrieval": True,
                    },
                )
            self.repair_prompts.append(prompt)
            return await super().generate_json(prompt, schema, **kwargs)

    tools = _MissingIntentRetryTools()
    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="How often should I water my Pata?",
        plant_hint=None,
    )

    assert tools._classifier_call_count == 2, "missing-field repair retry should run once"
    assert result["intent"] == "botanical"
    assert result["required_aspects"] == ["watering_frequency_or_trigger"]
    assert result["topic"] == "watering"
    assert result.get("care_classification") is not None
    assert result["care_classification"].source == "llm"
    assert not any("invalid output" in f for f in result.get("tool_failures", []))
    assert "intent" in tools.repair_prompts[1], (
        "repair prompt must explicitly list the missing `intent` field"
    )

def test_care_classifier_repair_prompt_includes_missing_fields_and_template() -> None:
    """The repair prompt must list missing required field names explicitly and
    include a complete schema-shaped JSON template so the model can repair the
    previous response without guessing the structure."""
    from app.assistant.graph import _care_classifier_repair_prompt

    state: dict = {
        "message": "How often should I water my Pata?",
        "plant_hint": "Pata",
        "plant_binomial_name": "Cotyledon tomentosa",
    }
    prompt = _care_classifier_repair_prompt(
        state,
        original_error="1 validation error for CareClassification\nintent\n  Field required",
        missing_fields=["intent"],
        previous_response={
            "language": "en",
            "answer_language": "en",
            "topic": "watering",
            "plant_reference": "Pata",
        },
    )

    assert "Missing required fields" in prompt
    assert "intent" in prompt
    assert "Return the response using exactly this JSON template" in prompt
    for required_field in (
        "language",
        "answer_language",
        "intent",
        "topic",
        "required_aspects",
        "plant_reference",
        "confidence",
        "needs_retrieval",
    ):
        assert f'"{required_field}"' in prompt, (
            f"repair prompt template must include {required_field!r}"
        )
    assert "Your previous response already contained" in prompt
    assert "KEEP them" in prompt

def test_care_classifier_repair_prompt_falls_back_to_error_text_scan() -> None:
    """When the caller does not pre-compute missing fields, the repair prompt
    builder must still recover them by scanning the error text against the
    known schema field names."""
    from pydantic import ValidationError

    from app.assistant.care_contracts import CareClassification
    from app.assistant.graph import (
        CARE_CLASSIFIER_SCHEMA,
        _care_classifier_repair_prompt,
        _extract_missing_field_names,
    )

    state: dict = {
        "message": "How often should I water my Pata?",
        "plant_hint": "Pata",
    }
    try:
        CareClassification.model_validate({"topic": "watering", "language": "en"})
    except ValidationError as exc:
        extracted = _extract_missing_field_names(exc, schema=CARE_CLASSIFIER_SCHEMA)
    else:
        extracted = []

    assert "intent" in extracted
    assert "confidence" in extracted

    prompt = _care_classifier_repair_prompt(
        state, original_error="missing intent and confidence", missing_fields=None
    )
    assert "Missing required fields" in prompt
    assert "intent" in prompt
    assert "confidence" in prompt

async def test_classifier_invalid_output_metric_increments_on_invalid_first_response() -> None:
    """The classifier_invalid_output_total counter must increment and appear
    in the prometheus output when the LLM classifier returns a structurally
    invalid object that cannot be repaired."""
    from httpx import ASGITransport, AsyncClient

    from app.main import app
    from app.observability.metrics import metrics_registry

    baseline = metrics_registry.classifier_invalid_output_total
    tools = FakeTools(
        classifier_data={
            "language": "en",
            "answer_language": "en",
            "intent": "not_a_valid_intent",
            "topic": "watering",
            "required_aspects": ["watering_frequency_or_trigger"],
            "confidence": 0.95,
            "needs_retrieval": True,
        }
    )

    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="How often should I water my Pata?",
        plant_hint=None,
    )

    assert result["intent"] == "botanical"
    assert metrics_registry.classifier_invalid_output_total >= baseline + 1

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/metrics")

    assert response.status_code == 200
    assert "fotosintesis_classifier_invalid_output_total" in response.text
    assert (
        f"fotosintesis_classifier_invalid_output_total {metrics_registry.classifier_invalid_output_total}"
        in response.text
    )

async def test_classifier_invalid_output_metric_increments_on_missing_required_field() -> None:
    """The classifier_invalid_output_total counter must increment when the
    first response is missing a required field (e.g. intent) even if the
    repair retry eventually succeeds."""
    from app.observability.metrics import metrics_registry

    baseline = metrics_registry.classifier_invalid_output_total

    class _MissingFieldRetryTools(FakeTools):
        def __init__(self) -> None:
            super().__init__()
            self._classifier_call_count = 0

        async def generate_json(self, prompt: str, schema: dict, **kwargs) -> ToolResult:
            self._classifier_call_count += 1
            if self._classifier_call_count == 1:
                return ToolResult(
                    ok=True,
                    data={
                        "language": "en",
                        "answer_language": "en",
                        "topic": "watering",
                        "required_aspects": ["watering_frequency_or_trigger"],
                        "plant_reference": "Pata",
                        "confidence": 0.9,
                        "needs_retrieval": True,
                    },
                )
            return await super().generate_json(prompt, schema, **kwargs)

    tools = _MissingFieldRetryTools()
    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="How often should I water my Pata?",
        plant_hint=None,
    )

    assert tools._classifier_call_count == 2
    assert result["intent"] == "botanical"
    assert metrics_registry.classifier_invalid_output_total >= baseline + 1

async def test_classifier_invalid_output_log_payload_structure(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The classifier_invalid_output log event must emit a payload with
    ctx_event='classifier_invalid_output', bounded ctx_missing_field_count,
    and a truncated ctx_error; no raw model output or secrets."""
    import logging

    caplog.set_level(logging.INFO, logger="app.assistant.graph")

    class _MissingIntentTools(FakeTools):
        def __init__(self) -> None:
            super().__init__()
            self._classifier_call_count = 0

        async def generate_json(self, prompt: str, schema: dict, **kwargs) -> ToolResult:
            self._classifier_call_count += 1
            if self._classifier_call_count == 1:
                return ToolResult(
                    ok=True,
                    data={
                        "language": "en",
                        "answer_language": "en",
                        "topic": "watering",
                        "required_aspects": ["watering_frequency_or_trigger"],
                        "plant_reference": "Pata",
                        "confidence": 0.9,
                        "needs_retrieval": True,
                    },
                )
            return await super().generate_json(prompt, schema, **kwargs)

    await AssistantGraph(_MissingIntentTools()).run(
        user_id=uuid4(),
        message="How often should I water my Monstera?",
        plant_hint=None,
    )

    log_record = next(
        (r for r in caplog.records if r.message == "classifier invalid output"),
        None,
    )
    assert log_record is not None, "classifier_invalid_output log event not emitted"

    record_dict = log_record.__dict__
    assert record_dict.get("ctx_event") == "classifier_invalid_output"
    assert record_dict.get("ctx_stage") == "before_repair"
    missing_fields = record_dict.get("ctx_missing_fields", [])
    assert isinstance(missing_fields, list)
    assert record_dict.get("ctx_missing_field_count") == len(missing_fields)
    assert record_dict.get("ctx_missing_field_count", 0) <= 10
    assert "intent" in missing_fields
    error_val = record_dict.get("ctx_error", "")
    assert isinstance(error_val, str)
    assert len(error_val) <= 240
    assert record_dict.get("ctx_trace_id") is not None

async def test_classifier_call_uses_model_purpose_signal_not_provider_specific_model_id() -> None:
    """The classifier call must signal `model_purpose='classifier'` and never
    forward a provider-specific model id (like 'gemini-2.5-flash-lite' or
    'gpt-5.4-mini') into the provider chain. Otherwise, when MODEL_PROVIDERS
    triggers a runtime fallback, the fallback provider would receive the
    primary provider's classifier id."""
    captured_kwargs: list[dict] = []

    class _KwargsCapturingTools(FakeTools):
        async def generate_json(self, prompt: str, schema: dict, **kwargs) -> ToolResult:
            captured_kwargs.append(dict(kwargs))
            return await super().generate_json(prompt, schema, **kwargs)

    await AssistantGraph(_KwargsCapturingTools()).run(
        user_id=uuid4(),
        message="How often should I water my Pata?",
        plant_hint=None,
        plant_binomial_name=CONFIRMED_BINOMIAL,
    )

    assert captured_kwargs, "classifier should have invoked generate_json"
    for kwargs in captured_kwargs:
        assert "model" not in kwargs, (
            "Classifier call must not forward a provider-specific model id; "
            f"got kwargs={kwargs!r}"
        )
        assert kwargs.get("model_purpose") == "classifier", (
            "Classifier call must signal model_purpose='classifier'; "
            f"got kwargs={kwargs!r}"
        )

async def test_classifier_gemini_503_falls_back_to_openai_with_openai_shaped_model_id() -> None:
    """End-to-end regression: when the primary Gemini provider raises 503
    during the classifier call, the OpenAI fallback must receive an
    OpenAI-shaped model id, never a Gemini one."""
    from app.providers.fallback import circuit_breaker
    from app.providers.fallback_context import clear_provider_fallbacks
    from app.providers.gemini import GeminiProviderError
    from app.providers.interfaces import ModelProvider
    from app.providers.types import JsonGenerationResult
    from app.providers.wrappers import ModelProviderFallbackWrapper

    circuit_breaker.clear()
    clear_provider_fallbacks()

    openai_calls: list[dict] = []

    class _FailFirstGeminiProvider(ModelProvider):
        provider_name = "gemini-model-test"

        def __init__(self, *, fail_first: int) -> None:
            self.model = "gemini-2.5-flash"
            self.classifier_model = "gemini-2.5-flash-lite"
            self._fail_first = fail_first
            self._attempt_count = 0

        async def generate_text(self, prompt: str, **kwargs):
            self._attempt_count += 1
            raise GeminiProviderError(
                "503 UNAVAILABLE",
                original_exception=RuntimeError("simulated 503"),
            )

        async def generate_json(self, prompt, schema, **kwargs):
            self._attempt_count += 1
            if self._attempt_count <= self._fail_first:
                raise GeminiProviderError(
                    "503 UNAVAILABLE",
                    original_exception=RuntimeError("simulated 503"),
                )
            return JsonGenerationResult(
                provider=self.provider_name,
                model=self.classifier_model,
                data={"ok": True},
            )

        async def judge_response(self, payload, rubric, **kwargs):
            raise NotImplementedError

    class _RecordingOpenAIProvider(ModelProvider):
        provider_name = "openai-model-test"

        def __init__(self) -> None:
            self.model = "gpt-5.4"
            self.classifier_model = "gpt-5.4-mini"

        def _resolve(self, kwargs: dict) -> str:
            explicit = kwargs.pop("model", None)
            if explicit is not None:
                return explicit
            purpose = kwargs.pop("model_purpose", None)
            if purpose == "classifier":
                return self.classifier_model
            return self.model

        async def generate_text(self, prompt: str, **kwargs):
            selected = self._resolve(kwargs)
            openai_calls.append({"op": "generate_text", "kwargs": kwargs})
            from app.providers.types import TextGenerationResult
            return TextGenerationResult(
                provider=self.provider_name, model=selected, text="ok"
            )

        async def generate_json(self, prompt, schema, **kwargs):
            selected = self._resolve(kwargs)
            openai_calls.append({"op": "generate_json", "kwargs": kwargs})
            return JsonGenerationResult(
                provider=self.provider_name,
                model=selected,
                data={"language": "en", "answer_language": "en",
                      "intent": "plant_care_question", "topic": "watering",
                      "required_aspects": ["watering_frequency_or_trigger"],
                      "plant_reference": "Pata", "confidence": 0.9,
                      "needs_retrieval": True},
            )

        async def judge_response(self, payload, rubric, **kwargs):
            raise NotImplementedError

    gemini = _FailFirstGeminiProvider(fail_first=1)
    openai = _RecordingOpenAIProvider()
    wrapper = ModelProviderFallbackWrapper([gemini, openai])

    class _ClassifierOnlyTools(FakeTools):
        def __init__(self) -> None:
            super().__init__()
            self.providers = SimpleNamespace(
                model=wrapper,
                embeddings=object(),
                trefle=object(),
                perenual=object(),
            )

        async def generate_json(self, prompt: str, schema: dict, **kwargs) -> ToolResult:
            try:
                result = await wrapper.generate_json(prompt, schema, **kwargs)
                return ToolResult(ok=True, data=result.data)
            except Exception as exc:
                return ToolResult(ok=False, error=str(exc))

    result = await AssistantGraph(_ClassifierOnlyTools()).run(
        user_id=uuid4(),
        message="How often should I water my Pata?",
        plant_hint=None,
        plant_binomial_name=CONFIRMED_BINOMIAL,
    )

    assert openai_calls, "OpenAI fallback should have been called after Gemini 503"
    for call in openai_calls:
        kwargs = call["kwargs"]
        assert "model" not in kwargs, (
            "OpenAI fallback must not receive a provider-specific model id from the caller; "
            f"got kwargs={kwargs!r}"
        )
        assert "model_purpose" not in kwargs, (
            "OpenAI fallback must not receive model_purpose as an unknown SDK argument; "
            f"got kwargs={kwargs!r}"
        )

    assert result["intent"] == "botanical"
    assert result["topic"] == "watering"

async def test_llm_classifier_success_preserves_detailed_topic_and_aspects() -> None:
    tools = FakeTools(
        classifier_data={
            "language": "en",
            "answer_language": "en",
            "intent": "plant_care_question",
            "topic": "watering",
            "required_aspects": ["watering_frequency_or_trigger"],
            "plant_reference": "Pata",
            "confidence": 0.92,
            "needs_retrieval": True,
        }
    )

    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="How often should I water my Pata?",
        plant_hint=None,
        plant_binomial_name=CONFIRMED_BINOMIAL,
    )

    assert result["intent"] == "botanical"
    assert result["topic"] == "watering"
    assert result["required_aspects"] == ["watering_frequency_or_trigger"]
    assert result["answer_language"] == "en"
    assert not any("classifier" in f for f in result["tool_failures"])

async def test_llm_classifier_success_preserves_toxicity_aspects() -> None:
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
        }
    )

    result = await AssistantGraph(tools).run(
        user_id=uuid4(),
        message="Is it toxic to cats?",
        plant_hint=None,
        plant_binomial_name=CONFIRMED_BINOMIAL,
    )

    assert result["topic"] == "toxicity_safety"
    assert result["required_aspects"] == ["toxicity_pet_safety"]

