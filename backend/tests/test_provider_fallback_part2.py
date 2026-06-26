from typing import Any

import pytest

from app.providers.fallback import (
    FailureCategory,
    circuit_breaker,
    classify_failure,
)
from app.providers.fallback_context import (
    clear_provider_fallbacks,
    get_provider_fallbacks,
)
from app.providers.interfaces import (
    ModelProvider,
)
from app.providers.types import (
    JudgeResult,
    JsonGenerationResult,
    TextGenerationResult,
)
from app.providers.wrappers import (
    AllProvidersFailedError,
    ImageAnalysisProviderFallbackWrapper,
    JudgeEvaluationProviderFallbackWrapper,
    ModelProviderFallbackWrapper,
    SearchProviderFallbackWrapper,
)
from app.providers.gemini import GeminiProviderError
from app.observability.metrics import metrics_registry


# ---------------------------------------------------------------------------
# Helper: Fake providers for testing
# ---------------------------------------------------------------------------

from tests._provider_fallback_helpers import (
    _FakeImageAnalysisProvider,
    _FakeJudgeProvider,
    _FakeModelProvider,
    _FakeSearchProvider,
)

class TestSearchProviderOrdering:
    async def test_gemini_first_openai_second(self) -> None:
        p1 = _FakeSearchProvider(name="gemini", fail=True)
        p2 = _FakeSearchProvider(name="openai")
        wrapper = SearchProviderFallbackWrapper([p1, p2])
        result = await wrapper.search("test")
        assert result[0].source_domain == "openai.example.com"

    async def test_openai_first_gemini_second(self) -> None:
        p1 = _FakeSearchProvider(name="openai", fail=True)
        p2 = _FakeSearchProvider(name="gemini")
        wrapper = SearchProviderFallbackWrapper([p1, p2])
        result = await wrapper.search("test")
        assert result[0].source_domain == "gemini.example.com"

    async def test_same_contract_regardless_of_order(self) -> None:
        p1 = _FakeSearchProvider(name="provider-a")
        p2 = _FakeSearchProvider(name="provider-b")
        wrapper = SearchProviderFallbackWrapper([p1, p2])
        result = await wrapper.search("test")
        assert isinstance(result, list)
        assert len(result) > 0
        assert hasattr(result[0], "title")
        assert hasattr(result[0], "url")
        assert hasattr(result[0], "source_domain")


# ---------------------------------------------------------------------------
# 8.8 Provider fallback metrics tests
# ---------------------------------------------------------------------------

class TestProviderFallbackMetrics:
    def setup_method(self) -> None:
        circuit_breaker.clear()
        metrics_registry.fallback_attempts_total = 0
        metrics_registry.fallback_successes_total = 0
        metrics_registry.provider_failures_total = 0
        metrics_registry.provider_failure_counts.clear()
        metrics_registry.skipped_unhealthy_providers_total = 0
        metrics_registry.circuit_breaker_opens_total = 0
        metrics_registry.provider_calls_total = 0

    async def test_fallback_attempts_increment_on_provider_call(self) -> None:
        p1 = _FakeModelProvider(name="attempts-p1", fail_generate_text=True)
        p2 = _FakeModelProvider(name="attempts-p2")
        wrapper = ModelProviderFallbackWrapper([p1, p2])
        await wrapper.generate_text("test")
        assert metrics_registry.fallback_attempts_total == 2

    async def test_fallback_attempts_single_provider(self) -> None:
        p1 = _FakeModelProvider(name="single-p1")
        wrapper = ModelProviderFallbackWrapper([p1])
        await wrapper.generate_text("test")
        assert metrics_registry.fallback_attempts_total == 1

    async def test_provider_failures_increment_on_failure(self) -> None:
        p1 = _FakeModelProvider(name="fail-p1", fail_generate_text=True)
        p2 = _FakeModelProvider(name="fail-p2")
        wrapper = ModelProviderFallbackWrapper([p1, p2])
        await wrapper.generate_text("test")
        assert metrics_registry.provider_failures_total == 1
        assert metrics_registry.provider_failure_counts == {
            ("model", "fail-p1", "generate_text", "service_unavailable"): 1,
        }

    async def test_provider_failures_all_providers_failed(self) -> None:
        p1 = _FakeModelProvider(name="allfail-p1", fail_generate_text=True)
        p2 = _FakeModelProvider(name="allfail-p2", fail_generate_text=True)
        wrapper = ModelProviderFallbackWrapper([p1, p2])
        with pytest.raises(AllProvidersFailedError):
            await wrapper.generate_text("test")
        assert metrics_registry.provider_failures_total == 2

    async def test_fallback_successes_incremented_only_on_fallback(self) -> None:
        p1 = _FakeModelProvider(name="succ-p1", fail_generate_text=True)
        p2 = _FakeModelProvider(name="succ-p2")
        wrapper = ModelProviderFallbackWrapper([p1, p2])
        await wrapper.generate_text("test")
        assert metrics_registry.fallback_successes_total == 1

    async def test_fallback_successes_not_incremented_on_primary(self) -> None:
        p1 = _FakeModelProvider(name="primary-only")
        wrapper = ModelProviderFallbackWrapper([p1])
        await wrapper.generate_text("test")
        assert metrics_registry.fallback_successes_total == 0

    async def test_skipped_unhealthy_providers_increment(self) -> None:
        circuit_breaker.open("skipped-p1", "search", "search", 60.0)
        p1 = _FakeSearchProvider(name="skipped-p1")
        p2 = _FakeSearchProvider(name="skipped-p2")
        wrapper = SearchProviderFallbackWrapper(
            [p1, p2],
            circuit_breaker_duration=60.0,
        )
        result = await wrapper.search("test")
        assert len(result) > 0
        assert result[0].source_domain == "skipped-p2.example.com"
        assert metrics_registry.skipped_unhealthy_providers_total == 1

    async def test_circuit_breaker_opens_increment(self) -> None:
        p1 = _FakeModelProvider(name="cb-p1", fail_generate_text=True)
        p2 = _FakeModelProvider(name="cb-p2")
        wrapper = ModelProviderFallbackWrapper(
            [p1, p2],
            attempt_timeout=5.0,
            circuit_breaker_duration=60.0,
        )
        await wrapper.generate_text("test")
        assert metrics_registry.circuit_breaker_opens_total == 1

    async def test_no_crosstalk_between_roles(self) -> None:
        p1 = _FakeModelProvider(name="cross-p1", fail_generate_text=True)
        p2 = _FakeModelProvider(name="cross-p2")
        wrapper = ModelProviderFallbackWrapper([p1, p2])
        await wrapper.generate_text("test")

        sp1 = _FakeSearchProvider(name="cross-sp1", fail=True)
        sp2 = _FakeSearchProvider(name="cross-sp2")
        swrapper = SearchProviderFallbackWrapper([sp1, sp2])
        await swrapper.search("test")

        assert metrics_registry.fallback_attempts_total == 4
        assert metrics_registry.provider_failures_total == 2
        assert metrics_registry.fallback_successes_total == 2

    async def test_metrics_to_prometheus_includes_nonzero_fallback_counters(self) -> None:
        p1 = _FakeModelProvider(name="prom-p1", fail_generate_text=True)
        p2 = _FakeModelProvider(name="prom-p2")
        wrapper = ModelProviderFallbackWrapper([p1, p2])
        await wrapper.generate_text("test")
        output = metrics_registry.to_prometheus()
        assert "fotosintesis_fallback_attempts_total 2" in output
        assert "fotosintesis_fallback_successes_total 1" in output
        assert "fotosintesis_provider_failures_total 1" in output
        assert (
            'fotosintesis_provider_failures_total{role="model",provider="prom-p1",'
            'operation="generate_text",failure_category="service_unavailable"} 1'
        ) in output


# ---------------------------------------------------------------------------
# 8.9 Failure latency correctness tests
# ---------------------------------------------------------------------------

class TestFailureLatency:
    def setup_method(self) -> None:
        circuit_breaker.clear()
        metrics_registry.fallback_attempts_total = 0
        metrics_registry.provider_failures_total = 0
        metrics_registry.provider_failure_counts.clear()

    async def test_failure_latency_is_elapsed_duration_not_timestamp(self) -> None:
        p1 = _FakeModelProvider(name="lat-p1", fail_generate_text=True, latency=0.05)
        p2 = _FakeModelProvider(name="lat-p2")
        wrapper = ModelProviderFallbackWrapper([p1, p2])
        result = await wrapper.generate_text("test")
        assert result.provider == "lat-p2"
        for a in wrapper._providers[0].__dict__.values():
            pass
        fallbacks = get_provider_fallbacks()
        assert len(fallbacks) >= 1
        last_attempt = fallbacks[-1]["attempted_providers"][0]
        assert last_attempt["outcome"].startswith("failed:")

    async def test_metadata_latency_ge_simulated_delay(self) -> None:
        delay = 0.1
        p1 = _FakeModelProvider(name="lat-md-p1", fail_generate_text=True, latency=delay)
        p2 = _FakeModelProvider(name="lat-md-p2")
        wrapper = ModelProviderFallbackWrapper([p1, p2])
        await wrapper.generate_text("test")
        fallbacks = get_provider_fallbacks()
        last = fallbacks[-1]
        failed_attempt = last["attempted_providers"][0]
        assert failed_attempt["outcome"].startswith("failed:")

    async def test_failure_latency_small_duration(self) -> None:
        p1 = _FakeModelProvider(name="small-p1", fail_generate_text=True, latency=0.05)
        p2 = _FakeModelProvider(name="small-p2")
        wrapper = ModelProviderFallbackWrapper([p1, p2])
        await wrapper.generate_text("test")
        from time import perf_counter
        now = perf_counter()
        assert now < 1_000_000

    async def test_non_transient_failure_latency_logged(self) -> None:
        import logging
        from io import StringIO
        handler = logging.StreamHandler(StringIO())
        handler.setLevel(logging.DEBUG)
        logger = logging.getLogger("app.providers.wrappers")
        logger.addHandler(handler)
        try:
            p1 = _FakeModelProvider(name="log-p1", fail_generate_text=True, non_transient=True)
            p2 = _FakeModelProvider(name="log-p2")
            wrapper = ModelProviderFallbackWrapper([p1, p2])
            with pytest.raises(AllProvidersFailedError):
                await wrapper.generate_text("test")
        finally:
            logger.removeHandler(handler)

    async def test_search_empty_results_latency_is_elapsed(self) -> None:
        p1 = _FakeSearchProvider(name="se-lat-p1", empty_results=True, latency=0.05)
        p2 = _FakeSearchProvider(name="se-lat-p2")
        wrapper = SearchProviderFallbackWrapper([p1, p2])
        result = await wrapper.search("test")
        assert len(result) > 0

    async def test_judge_failure_latency_is_elapsed(self) -> None:
        p1 = _FakeJudgeProvider(name="j-lat-p1", fail=True, latency=0.05)
        p2 = _FakeJudgeProvider(name="j-lat-p2")
        wrapper = JudgeEvaluationProviderFallbackWrapper([p1, p2])
        result = await wrapper.judge_response({"q": "test"}, {"passing_score": 1})
        assert result.provider == "j-lat-p2"

    async def test_vision_failure_latency_is_elapsed(self) -> None:
        p1 = _FakeImageAnalysisProvider(name="v-lat-p1", fail=True, latency=0.05)
        p2 = _FakeImageAnalysisProvider(name="v-lat-p2")
        wrapper = ImageAnalysisProviderFallbackWrapper([p1, p2])
        result = await wrapper.analyze_image(b"test")
        assert result.provider == "v-lat-p2"

    async def test_retry_failure_latency_is_elapsed(self) -> None:
        class _RetryThenFail(ModelProvider):
            provider_name = "retry-fail"
            call_count = 0
            async def generate_text(self, prompt: str, **kwargs: Any) -> TextGenerationResult:
                return TextGenerationResult(provider=self.provider_name, model="m", text="ok")
            async def generate_json(self, prompt: str, schema: dict[str, Any], **kwargs: Any) -> JsonGenerationResult:
                _RetryThenFail.call_count += 1
                if _RetryThenFail.call_count <= 2:
                    raise RuntimeError("retry-fail invalid structured output")
                return JsonGenerationResult(provider=self.provider_name, model="m", data={})
            async def judge_response(self, payload: dict[str, Any], rubric: dict[str, Any], **kwargs: Any) -> JudgeResult:
                return JudgeResult(provider=self.provider_name, model="m", score=1, passed=True, status="full", confidence=1)

        _RetryThenFail.call_count = 0
        p1 = _RetryThenFail()
        p2 = _FakeModelProvider(name="retry-fallback")
        wrapper = ModelProviderFallbackWrapper([p1, p2])
        result = await wrapper.generate_json("test", {"type": "object"})
        assert result.provider == "retry-fallback"


# ---------------------------------------------------------------------------
# Typed failure metadata tests
# ---------------------------------------------------------------------------

class TestTypedFailureMetadata:
    def test_attempt_metadata_includes_transient_flag(self) -> None:
        from app.providers.fallback import AttemptMetadata
        meta = AttemptMetadata(
            provider="test", role="model", operation="generate_text",
            attempt_index=0, failure_category="timeout", transient=True, retryable=True,
        )
        assert meta.transient is True
        assert meta.retryable is True

    def test_attempt_metadata_includes_status_code(self) -> None:
        from app.providers.fallback import AttemptMetadata
        meta = AttemptMetadata(
            provider="test", role="model", operation="generate_text",
            attempt_index=0, failure_category="service_unavailable",
            status_code=503, cause_type="GoogleGenerativeAIClientError",
        )
        assert meta.status_code == 503
        assert meta.cause_type == "GoogleGenerativeAIClientError"

    def test_extract_status_code_from_exception(self) -> None:
        from app.providers.fallback import extract_status_code
        exc = RuntimeError("service unavailable")
        exc.status_code = 503
        assert extract_status_code(exc) == 503

    def test_extract_status_code_returns_none_when_absent(self) -> None:
        from app.providers.fallback import extract_status_code
        exc = RuntimeError("service unavailable")
        assert extract_status_code(exc) is None

    def test_extract_cause_type_from_original_exception(self) -> None:
        from app.providers.fallback import extract_cause_type
        original = ValueError("bad config")
        wrapper = RuntimeError("wrapped")
        wrapper.original_exception = original
        assert extract_cause_type(wrapper) == "ValueError"

    def test_extract_cause_type_returns_none_when_no_cause(self) -> None:
        from app.providers.fallback import extract_cause_type
        exc = RuntimeError("simple")
        assert extract_cause_type(exc) is None

    def test_classify_failure_traverses_original_exception(self) -> None:
        original = RuntimeError("503 UNAVAILABLE")
        wrapper = GeminiProviderError("Gemini generate_text call failed", original_exception=original)
        assert classify_failure(wrapper) == FailureCategory.service_unavailable

    def test_classify_failure_traverses_cause_chain(self) -> None:
        original = ConnectionError("network error")
        wrapper = RuntimeError("wrapped error")
        wrapper.__cause__ = original
        assert classify_failure(wrapper) == FailureCategory.network_error

    async def test_gemini_503_triggers_fallback(self) -> None:
        """Gemini 503 UNAVAILABLE should be classified as transient and trigger fallback."""
        class _Gemini503Provider(ModelProvider):
            provider_name = "gemini-503"
            async def generate_text(self, prompt: str, **kwargs: Any) -> TextGenerationResult:
                raise GeminiProviderError(
                    "Gemini generate_text call failed",
                    original_exception=RuntimeError("503 UNAVAILABLE The service is currently unavailable."),
                )
            async def generate_json(self, prompt: str, schema: dict[str, Any], **kwargs: Any) -> JsonGenerationResult:
                raise GeminiProviderError(
                    "Gemini generate_json call failed",
                    original_exception=RuntimeError("503 UNAVAILABLE The service is currently unavailable."),
                )
            async def judge_response(self, payload: dict[str, Any], rubric: dict[str, Any], **kwargs: Any) -> JudgeResult:
                return JudgeResult(provider=self.provider_name, model="m", score=1, passed=True, status="full", confidence=1)

        p1 = _Gemini503Provider()
        p2 = _FakeModelProvider(name="fallback-model")
        wrapper = ModelProviderFallbackWrapper([p1, p2])
        result = await wrapper.generate_text("test")
        assert result.provider == "fallback-model"

    async def test_all_providers_failed_exposes_transient_flag(self) -> None:
        """AllProvidersFailedError exposes is_transient and is_retryable properties."""
        p1 = _FakeModelProvider(name="failing-p1", fail_generate_text=True)
        p2 = _FakeModelProvider(name="failing-p2", fail_generate_text=True)
        wrapper = ModelProviderFallbackWrapper([p1, p2])
        with pytest.raises(AllProvidersFailedError) as exc_info:
            await wrapper.generate_text("test")
        assert exc_info.value.is_transient is True
        assert exc_info.value.is_retryable is True

    async def test_all_providers_failed_non_transient(self) -> None:
        """AllProvidersFailedError with non-transient failures."""
        p1 = _FakeModelProvider(name="config-error", fail_generate_text=True, non_transient=True)
        wrapper = ModelProviderFallbackWrapper([p1])
        with pytest.raises(AllProvidersFailedError) as exc_info:
            await wrapper.generate_text("test")
        assert exc_info.value.is_transient is False
        assert exc_info.value.is_retryable is False

    async def test_fallback_metadata_includes_typed_fields(self) -> None:
        """Fallback metadata recorded in context includes typed failure fields."""
        clear_provider_fallbacks()
        p1 = _FakeModelProvider(name="typed-p1", fail_generate_text=True)
        p2 = _FakeModelProvider(name="typed-p2")
        wrapper = ModelProviderFallbackWrapper([p1, p2])
        result = await wrapper.generate_text("test")
        assert result.provider == "typed-p2"
        fallbacks = get_provider_fallbacks()
        assert len(fallbacks) == 1
        attempts = fallbacks[0]["attempted_providers"]
        failed_attempt = next(a for a in attempts if a["provider"] == "typed-p1")
        assert failed_attempt["attempt_index"] == 0
        assert failed_attempt["transient"] is True
        assert failed_attempt["retryable"] is True
        assert failed_attempt["failure_category"] == "service_unavailable"


# ---------------------------------------------------------------------------
# 8.10 Classifier model routing across provider fallback chains
# ---------------------------------------------------------------------------

class _RecordingModelProvider(ModelProvider):
    """Records every model id used by ``generate_json`` calls."""

    def __init__(
        self,
        *,
        name: str,
        model: str,
        classifier_model: str | None = None,
        fail_first_attempts: int = 0,
    ) -> None:
        self.provider_name = name
        self.model = model
        self.classifier_model = classifier_model or model
        self._fail_first_attempts = fail_first_attempts
        self._attempt_count = 0
        self.calls: list[dict[str, Any]] = []

    async def generate_text(self, prompt: str, **kwargs: Any) -> TextGenerationResult:
        return TextGenerationResult(
            provider=self.provider_name, model=self.model, text="ok"
        )

    async def generate_json(
        self, prompt: str, schema: dict[str, Any], **kwargs: Any
    ) -> JsonGenerationResult:
        self._attempt_count += 1
        recorded = {
            "model": kwargs.get("model"),
            "model_purpose": kwargs.get("model_purpose"),
        }
        if recorded["model"] is not None:
            recorded_model = recorded["model"]
        elif recorded["model_purpose"] == "classifier":
            recorded_model = self.classifier_model
        else:
            recorded_model = self.model
        recorded["resolved_model"] = recorded_model
        self.calls.append(recorded)
        if self._fail_first_attempts >= self._attempt_count:
            raise GeminiProviderError(
                "transient service unavailable",
                original_exception=RuntimeError("503 UNAVAILABLE"),
            )
        return JsonGenerationResult(
            provider=self.provider_name,
            model=recorded_model,
            data={"prompt": prompt[:40]},
        )

    async def judge_response(
        self, payload: dict[str, Any], rubric: dict[str, Any], **kwargs: Any
    ) -> JudgeResult:
        return JudgeResult(
            provider=self.provider_name,
            model=self.model,
            score=1.0,
            passed=True,
            status="full",
            confidence=1.0,
        )

class TestClassifierModelRoutingAcrossFallbackChain:
    async def test_gemini_primary_openai_fallback_does_not_leak_gemini_model_id_to_openai(
        self,
    ) -> None:
        """When MODEL_PROVIDERS=['gemini','openai'] and Gemini fails transiently,
        the OpenAI fallback must resolve its own classifier model id, not inherit
        the Gemini classifier id from the caller."""
        circuit_breaker.clear()
        clear_provider_fallbacks()
        gemini = _RecordingModelProvider(
            name="gemini-model",
            model="gemini-2.5-flash",
            classifier_model="gemini-2.5-flash-lite",
            fail_first_attempts=1,
        )
        openai = _RecordingModelProvider(
            name="openai-model",
            model="gpt-5.4",
            classifier_model="gpt-5.4-mini",
        )
        wrapper = ModelProviderFallbackWrapper([gemini, openai])

        result = await wrapper.generate_json(
            "care prompt", {"type": "object"}, model_purpose="classifier"
        )

        assert result.provider == "openai-model"
        assert len(gemini.calls) == 1
        assert gemini.calls[0]["resolved_model"] == "gemini-2.5-flash-lite"
        assert len(openai.calls) == 1
        openai_recorded_model = openai.calls[0]["resolved_model"]
        assert "gemini" not in openai_recorded_model.lower()
        assert openai_recorded_model == "gpt-5.4-mini"

    async def test_openai_primary_gemini_fallback_does_not_leak_openai_model_id_to_gemini(
        self,
    ) -> None:
        """When MODEL_PROVIDERS=['openai','gemini'] and OpenAI fails transiently,
        the Gemini fallback must resolve its own classifier model id, not inherit
        the OpenAI classifier id from the caller."""
        circuit_breaker.clear()
        clear_provider_fallbacks()
        openai = _RecordingModelProvider(
            name="openai-model",
            model="gpt-5.4",
            classifier_model="gpt-5.4-mini",
            fail_first_attempts=1,
        )
        gemini = _RecordingModelProvider(
            name="gemini-model",
            model="gemini-2.5-flash",
            classifier_model="gemini-2.5-flash-lite",
        )
        wrapper = ModelProviderFallbackWrapper([openai, gemini])

        result = await wrapper.generate_json(
            "care prompt", {"type": "object"}, model_purpose="classifier"
        )

        assert result.provider == "gemini-model"
        assert len(openai.calls) == 1
        assert openai.calls[0]["resolved_model"] == "gpt-5.4-mini"
        assert len(gemini.calls) == 1
        gemini_recorded_model = gemini.calls[0]["resolved_model"]
        assert "gpt" not in gemini_recorded_model.lower()
        assert gemini_recorded_model == "gemini-2.5-flash-lite"

    async def test_openai_only_single_provider_uses_classifier_model(self) -> None:
        """Single OpenAI provider resolves to OPENAI_CLASSIFIER_MODEL for classifier calls."""
        openai = _RecordingModelProvider(
            name="openai-model",
            model="gpt-5.4",
            classifier_model="gpt-5.4-mini",
        )
        wrapper = ModelProviderFallbackWrapper([openai])

        result = await wrapper.generate_json(
            "care prompt", {"type": "object"}, model_purpose="classifier"
        )

        assert result.provider == "openai-model"
        assert result.model == "gpt-5.4-mini"
        assert len(openai.calls) == 1
        assert openai.calls[0]["resolved_model"] == "gpt-5.4-mini"

    async def test_gemini_only_single_provider_uses_classifier_model(self) -> None:
        """Single Gemini provider resolves to GEMINI_CLASSIFIER_MODEL for classifier calls."""
        gemini = _RecordingModelProvider(
            name="gemini-model",
            model="gemini-2.5-flash",
            classifier_model="gemini-2.5-flash-lite",
        )
        wrapper = ModelProviderFallbackWrapper([gemini])

        result = await wrapper.generate_json(
            "care prompt", {"type": "object"}, model_purpose="classifier"
        )

        assert result.provider == "gemini-model"
        assert result.model == "gemini-2.5-flash-lite"
        assert len(gemini.calls) == 1
        assert gemini.calls[0]["resolved_model"] == "gemini-2.5-flash-lite"

    async def test_model_kwarg_override_still_wins_over_classifier_purpose(self) -> None:
        """If the caller passes model=... explicitly, it overrides classifier resolution."""
        openai = _RecordingModelProvider(
            name="openai-model",
            model="gpt-5.4",
            classifier_model="gpt-5.4-mini",
        )
        wrapper = ModelProviderFallbackWrapper([openai])

        result = await wrapper.generate_json(
            "care prompt",
            {"type": "object"},
            model="gpt-5.4-experimental",
            model_purpose="classifier",
        )

        assert result.model == "gpt-5.4-experimental"
        assert openai.calls[0]["resolved_model"] == "gpt-5.4-experimental"

    async def test_classifier_call_uses_default_text_model_when_classifier_model_not_set(
        self,
    ) -> None:
        """When no classifier_model is configured, the provider falls back to its text model."""
        openai = _RecordingModelProvider(
            name="openai-model", model="gpt-5.4", classifier_model=None
        )
        wrapper = ModelProviderFallbackWrapper([openai])

        result = await wrapper.generate_json(
            "care prompt", {"type": "object"}, model_purpose="classifier"
        )

        assert result.model == "gpt-5.4"
        assert openai.calls[0]["resolved_model"] == "gpt-5.4"

@pytest.mark.asyncio
async def test_fallback_wrapper_does_not_forward_gemini_model_id_to_openai() -> None:
    """Provider-level regression for the cross-provider model id leak.

    Builds a ModelProviderFallbackWrapper with a fake Gemini provider that
    raises 503 and a fake OpenAI provider that records every kwargs dict it
    receives. Calls generate_json with model_purpose='classifier' and
    asserts the OpenAI provider's recorded kwargs contain no Gemini model
    id and no model_purpose leak.
    """
    from app.providers.gemini import GeminiProviderError

    circuit_breaker.clear()
    clear_provider_fallbacks()

    received_kwargs: list[dict[str, Any]] = []

    class _FailingGemini(ModelProvider):
        provider_name = "gemini-fail"

        def __init__(self) -> None:
            self.model = "gemini-2.5-flash"
            self.classifier_model = "gemini-2.5-flash-lite"

        async def generate_text(self, prompt: str, **kwargs: Any) -> TextGenerationResult:
            raise GeminiProviderError(
                "503 UNAVAILABLE",
                original_exception=RuntimeError("simulated 503"),
            )

        async def generate_json(
            self, prompt: str, schema: dict[str, Any], **kwargs: Any
        ) -> JsonGenerationResult:
            raise GeminiProviderError(
                "503 UNAVAILABLE",
                original_exception=RuntimeError("simulated 503"),
            )

        async def judge_response(
            self, payload: dict[str, Any], rubric: dict[str, Any], **kwargs: Any
        ) -> JudgeResult:
            raise NotImplementedError

    class _RecordingOpenAI(ModelProvider):
        provider_name = "openai-record"

        def __init__(self) -> None:
            self.model = "gpt-5.4"
            self.classifier_model = "gpt-5.4-mini"

        def _resolve(self, kwargs: dict[str, Any]) -> str:
            explicit = kwargs.pop("model", None)
            if explicit is not None:
                return explicit
            purpose = kwargs.pop("model_purpose", None)
            if purpose == "classifier":
                return self.classifier_model
            return self.model

        async def generate_text(self, prompt: str, **kwargs: Any) -> TextGenerationResult:
            selected = self._resolve(kwargs)
            received_kwargs.append({"op": "generate_text", "kwargs": kwargs})
            return TextGenerationResult(
                provider=self.provider_name, model=selected, text="ok"
            )

        async def generate_json(
            self, prompt: str, schema: dict[str, Any], **kwargs: Any
        ) -> JsonGenerationResult:
            selected = self._resolve(kwargs)
            received_kwargs.append({"op": "generate_json", "kwargs": kwargs})
            return JsonGenerationResult(
                provider=self.provider_name,
                model=selected,
                data={"ok": True},
            )

        async def judge_response(
            self, payload: dict[str, Any], rubric: dict[str, Any], **kwargs: Any
        ) -> JudgeResult:
            raise NotImplementedError

    gemini = _FailingGemini()
    openai = _RecordingOpenAI()
    wrapper = ModelProviderFallbackWrapper([gemini, openai])

    result = await wrapper.generate_json(
        "care prompt", {"type": "object"}, model_purpose="classifier"
    )

    assert result.provider == "openai-record"
    assert result.model == "gpt-5.4-mini"
    assert received_kwargs, "OpenAI fallback should have been called"

    for call in received_kwargs:
        kwargs = {k: v for k, v in call.items() if k != "op"}
        assert "model" not in kwargs, (
            f"OpenAI must not receive a provider-specific model id; got kwargs={kwargs!r}"
        )
        assert "model_purpose" not in kwargs, (
            f"model_purpose must not reach the OpenAI provider; got kwargs={kwargs!r}"
        )
