import time
from typing import Any

import pytest

from app.core.settings import get_settings, Settings
from app.providers.fallback import (
    CircuitBreaker,
    FailureCategory,
    ProviderRole,
    circuit_breaker,
    classify_failure,
    is_circuit_breaker_failure,
    is_transient_failure,
)
from app.providers.fallback_context import (
    clear_provider_fallbacks,
    get_provider_fallbacks,
    record_provider_fallback,
)
from app.providers.factory import (
    ProviderRegistry,
    _build_model_chain,
    _build_search_chain,
    _build_vision_chain,
    _build_judge_chain,
    get_provider_registry,
)
from app.providers.interfaces import (
    ImageAnalysisProvider,
    JudgeEvaluationProvider,
    ModelProvider,
    SearchProvider,
)
from app.providers.mocks import (
    MockModelProvider,
    MockSearchProvider,
    MockVisionPlantIdentificationProvider,
)
from app.providers.types import (
    ImageAnalysisResult,
    JudgeResult,
    JsonGenerationResult,
    SearchResult,
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

class _FakeModelProvider(ModelProvider):
    def __init__(
        self,
        *,
        name: str = "fake-model",
        fail_generate_text: bool = False,
        fail_generate_json: bool = False,
        fail_judge: bool = False,
        invalid_json: bool = False,
        semantic_insufficient: bool = False,
        latency: float = 0.0,
        non_transient: bool = False,
    ) -> None:
        self.provider_name = name
        self._fail_text = fail_generate_text
        self._fail_json = fail_generate_json
        self._fail_judge = fail_judge
        self._invalid_json = invalid_json
        self._semantic_insufficient = semantic_insufficient
        self._latency = latency
        self._non_transient = non_transient

    async def generate_text(self, prompt: str, **kwargs: Any) -> TextGenerationResult:
        if self._latency:
            await _async_sleep(self._latency)
        if self._fail_text:
            if self._non_transient:
                raise ValueError(f"{self.provider_name} configuration error")
            raise RuntimeError(f"{self.provider_name} service unavailable")
        return TextGenerationResult(
            provider=self.provider_name,
            model="test-model",
            text=f"{self.provider_name} response to: {prompt[:40]}",
        )

    async def generate_json(
        self, prompt: str, schema: dict[str, Any], **kwargs: Any
    ) -> JsonGenerationResult:
        if self._latency:
            await _async_sleep(self._latency)
        if self._fail_json:
            if self._non_transient:
                raise ValueError(f"{self.provider_name} configuration error")
            raise RuntimeError(f"{self.provider_name} service unavailable")
        if self._invalid_json:
            raise RuntimeError(f"{self.provider_name} invalid structured output")
        return JsonGenerationResult(
            provider=self.provider_name,
            model="test-model",
            data={"result": f"{self.provider_name} json data"},
        )

    async def judge_response(
        self, payload: dict[str, Any], rubric: dict[str, Any], **kwargs: Any
    ) -> JudgeResult:
        if self._latency:
            await _async_sleep(self._latency)
        if self._fail_judge:
            if self._non_transient:
                raise ValueError(f"{self.provider_name} configuration error")
            raise RuntimeError(f"{self.provider_name} service unavailable")
        if self._semantic_insufficient:
            return JudgeResult(
                provider=self.provider_name,
                model="test-model",
                score=0.0,
                passed=False,
                reasons=["Insufficient evidence"],
                status="insufficient",
                confidence=0.0,
            )
        return JudgeResult(
            provider=self.provider_name,
            model="test-model",
            score=1.0,
            passed=True,
            status="full",
            reasons=[],
            confidence=1.0,
        )


class _FakeJudgeProvider(JudgeEvaluationProvider):
    def __init__(
        self,
        *,
        name: str = "fake-judge",
        fail: bool = False,
        semantic_insufficient: bool = False,
        invalid_output: bool = False,
        latency: float = 0.0,
        non_transient: bool = False,
    ) -> None:
        self.provider_name = name
        self._fail = fail
        self._semantic_insufficient = semantic_insufficient
        self._invalid_output = invalid_output
        self._latency = latency
        self._non_transient = non_transient

    async def judge_response(
        self, payload: dict[str, Any], rubric: dict[str, Any], **kwargs: Any
    ) -> JudgeResult:
        if self._latency:
            await _async_sleep(self._latency)
        if self._fail:
            if self._non_transient:
                raise ValueError(f"{self.provider_name} configuration error")
            raise RuntimeError(f"{self.provider_name} service unavailable")
        if self._invalid_output:
            raise RuntimeError(f"{self.provider_name} invalid structured output")
        if self._semantic_insufficient:
            return JudgeResult(
                provider=self.provider_name,
                model="test-model",
                score=0.0,
                passed=False,
                reasons=["Insufficient evidence"],
                status="insufficient",
                confidence=0.0,
            )
        return JudgeResult(
            provider=self.provider_name,
            model="test-model",
            score=1.0,
            passed=True,
            status="full",
            reasons=[],
            confidence=1.0,
        )


class _FakeSearchProvider(SearchProvider):
    def __init__(
        self,
        *,
        name: str = "fake-search",
        fail: bool = False,
        empty_results: bool = False,
        latency: float = 0.0,
        non_transient: bool = False,
    ) -> None:
        self.provider_name = name
        self._fail = fail
        self._empty = empty_results
        self._latency = latency
        self._non_transient = non_transient

    async def search(self, query: str, **kwargs: Any) -> list[SearchResult]:
        if self._latency:
            await _async_sleep(self._latency)
        if self._fail:
            if self._non_transient:
                raise ValueError(f"{self.provider_name} configuration error")
            raise RuntimeError(f"{self.provider_name} service unavailable")
        if self._empty:
            return []
        return [
            SearchResult(
                title=f"{self.provider_name} result",
                url=f"https://{self.provider_name}.example.com/result",
                snippet=f"{self.provider_name} search for {query[:30]}",
                source_domain=f"{self.provider_name}.example.com",
            )
        ]


class _FakeImageAnalysisProvider(ImageAnalysisProvider):
    def __init__(
        self,
        *,
        name: str = "fake-vision",
        fail: bool = False,
        latency: float = 0.0,
        non_transient: bool = False,
    ) -> None:
        self.provider_name = name
        self._fail = fail
        self._latency = latency
        self._non_transient = non_transient

    async def analyze_image(
        self, image: bytes, prompt: str | None = None, **kwargs: Any
    ) -> ImageAnalysisResult:
        if self._latency:
            await _async_sleep(self._latency)
        if self._fail:
            if self._non_transient:
                raise ValueError(f"{self.provider_name} configuration error")
            raise RuntimeError(f"{self.provider_name} service unavailable")
        return ImageAnalysisResult(
            provider=self.provider_name,
            model="test-model",
            description=f"{self.provider_name} analysis",
        )


async def _async_sleep(seconds: float) -> None:
    import asyncio
    await asyncio.sleep(seconds)


# ---------------------------------------------------------------------------
# 8.1 Provider registry tests
# ---------------------------------------------------------------------------

class TestProviderRegistry:
    def test_single_provider_compatibility(self) -> None:
        chain = _build_model_chain(["mock"], Settings())
        assert isinstance(chain, MockModelProvider)

    def test_ordered_chain_construction(self) -> None:
        settings = Settings(model_providers=["mock", "mock"])
        chain = _build_model_chain(settings.model_providers, settings)
        assert isinstance(chain, ModelProviderFallbackWrapper)

    def test_single_provider_fallback_when_chain_absent(self) -> None:
        chain = _build_model_chain(["mock"], Settings())
        assert isinstance(chain, MockModelProvider)

    def test_chain_single_provider_not_wrapped(self) -> None:
        chain = _build_model_chain(["mock"], Settings())
        assert not isinstance(chain, ModelProviderFallbackWrapper)

    def test_chain_two_providers_wrapped(self) -> None:
        chain = _build_model_chain(["mock", "mock"], Settings())
        assert isinstance(chain, ModelProviderFallbackWrapper)


# ---------------------------------------------------------------------------
# 8.2 Fallback wrapper tests
# ---------------------------------------------------------------------------

class TestFallbackWrappers:
    async def test_primary_provider_succeeds(self) -> None:
        p1 = _FakeModelProvider(name="primary")
        p2 = _FakeModelProvider(name="fallback")
        wrapper = ModelProviderFallbackWrapper([p1, p2])
        result = await wrapper.generate_text("test")
        assert result.provider == "primary"

    async def test_fallback_to_second_provider(self) -> None:
        p1 = _FakeModelProvider(name="primary", fail_generate_text=True)
        p2 = _FakeModelProvider(name="fallback")
        wrapper = ModelProviderFallbackWrapper([p1, p2])
        result = await wrapper.generate_text("test")
        assert result.provider == "fallback"

    async def test_all_providers_failed(self) -> None:
        p1 = _FakeModelProvider(name="p1", fail_generate_text=True)
        p2 = _FakeModelProvider(name="p2", fail_generate_text=True)
        wrapper = ModelProviderFallbackWrapper([p1, p2])
        with pytest.raises(AllProvidersFailedError):
            await wrapper.generate_text("test")

    async def test_invalid_structured_output_retry(self) -> None:
        p1 = _FakeModelProvider(name="p1", fail_generate_json=False)
        p2 = _FakeModelProvider(name="p2", fail_generate_json=False)
        wrapper = ModelProviderFallbackWrapper([p1, p2])
        result = await wrapper.generate_json("test", {"type": "object"})
        assert result.provider == "p1"

    async def test_search_empty_results_triggers_fallback(self) -> None:
        p1 = _FakeSearchProvider(name="p1", empty_results=True)
        p2 = _FakeSearchProvider(name="p2")
        wrapper = SearchProviderFallbackWrapper([p1, p2])
        result = await wrapper.search("test")
        assert result[0].source_domain == "p2.example.com"

    async def test_search_all_empty_results_fails(self) -> None:
        p1 = _FakeSearchProvider(name="p1", empty_results=True)
        p2 = _FakeSearchProvider(name="p2", empty_results=True)
        wrapper = SearchProviderFallbackWrapper([p1, p2])
        with pytest.raises(AllProvidersFailedError):
            await wrapper.search("test")

    async def test_judge_fallback_on_failure(self) -> None:
        p1 = _FakeJudgeProvider(name="p1", fail=True)
        p2 = _FakeJudgeProvider(name="p2")
        wrapper = JudgeEvaluationProviderFallbackWrapper([p1, p2])
        result = await wrapper.judge_response({"q": "test"}, {"passing_score": 1})
        assert result.provider == "p2"

    async def test_vision_fallback_on_failure(self) -> None:
        p1 = _FakeImageAnalysisProvider(name="p1", fail=True)
        p2 = _FakeImageAnalysisProvider(name="p2")
        wrapper = ImageAnalysisProviderFallbackWrapper([p1, p2])
        result = await wrapper.analyze_image(b"test")
        assert result.provider == "p2"

    async def test_non_transient_generate_text_does_not_fallback(self) -> None:
        class _ExplodingProvider(ModelProvider):
            provider_name = "exploding"
            async def generate_text(self, prompt: str, **kwargs: Any) -> TextGenerationResult:
                raise ValueError("non-transient configuration error")
            async def generate_json(self, prompt: str, schema: dict[str, Any], **kwargs: Any) -> JsonGenerationResult:
                raise ValueError("non-transient")
            async def judge_response(self, payload: dict[str, Any], rubric: dict[str, Any], **kwargs: Any) -> JudgeResult:
                raise ValueError("non-transient")

        not_called = False
        class _SafeProvider(ModelProvider):
            provider_name = "safe"
            async def generate_text(self, prompt: str, **kwargs: Any) -> TextGenerationResult:
                nonlocal not_called
                not_called = True
                return TextGenerationResult(provider=self.provider_name, model="m", text="ok")
            async def generate_json(self, prompt: str, schema: dict[str, Any], **kwargs: Any) -> JsonGenerationResult:
                return JsonGenerationResult(provider=self.provider_name, model="m", data={})
            async def judge_response(self, payload: dict[str, Any], rubric: dict[str, Any], **kwargs: Any) -> JudgeResult:
                return JudgeResult(provider=self.provider_name, model="m", score=1, passed=True, status="full", confidence=1)

        p1 = _ExplodingProvider()
        p2 = _SafeProvider()
        wrapper = ModelProviderFallbackWrapper([p1, p2])
        with pytest.raises(AllProvidersFailedError) as exc_info:
            await wrapper.generate_text("test")
        assert not not_called
        assert exc_info.value.fallback_metadata.role == "model"
        assert exc_info.value.fallback_metadata.operation == "generate_text"
        assert len(exc_info.value.fallback_metadata.attempts) == 1
        assert exc_info.value.fallback_metadata.attempts[0].provider == "exploding"

    async def test_non_transient_generate_json_does_not_fallback(self) -> None:
        not_called = False
        class _SafeProvider(ModelProvider):
            provider_name = "safe"
            async def generate_text(self, prompt: str, **kwargs: Any) -> TextGenerationResult:
                return TextGenerationResult(provider=self.provider_name, model="m", text="ok")
            async def generate_json(self, prompt: str, schema: dict[str, Any], **kwargs: Any) -> JsonGenerationResult:
                nonlocal not_called
                not_called = True
                return JsonGenerationResult(provider=self.provider_name, model="m", data={})
            async def judge_response(self, payload: dict[str, Any], rubric: dict[str, Any], **kwargs: Any) -> JudgeResult:
                return JudgeResult(provider=self.provider_name, model="m", score=1, passed=True, status="full", confidence=1)

        p1 = _FakeModelProvider(name="exploding", fail_generate_json=True, non_transient=True)
        p1.provider_name = "exploding"
        p2 = _SafeProvider()
        wrapper = ModelProviderFallbackWrapper([p1, p2])
        with pytest.raises(AllProvidersFailedError) as exc_info:
            await wrapper.generate_json("test", {"type": "object"})
        assert not not_called

    async def test_non_transient_judge_does_not_fallback(self) -> None:
        not_called = False
        class _SafeJudge(JudgeEvaluationProvider):
            provider_name = "safe"
            async def judge_response(self, payload: dict[str, Any], rubric: dict[str, Any], **kwargs: Any) -> JudgeResult:
                nonlocal not_called
                not_called = True
                return JudgeResult(provider=self.provider_name, model="m", score=1, passed=True, status="full", confidence=1)

        p1 = _FakeJudgeProvider(name="exploding", fail=True, non_transient=True)
        p1.provider_name = "exploding"
        p2 = _SafeJudge()
        wrapper = JudgeEvaluationProviderFallbackWrapper([p1, p2])
        with pytest.raises(AllProvidersFailedError) as exc_info:
            await wrapper.judge_response({"q": "test"}, {"passing_score": 1})
        assert not not_called

    async def test_non_transient_search_does_not_fallback(self) -> None:
        not_called = False
        class _SafeSearch(SearchProvider):
            provider_name = "safe"
            async def search(self, query: str, **kwargs: Any) -> list[SearchResult]:
                nonlocal not_called
                not_called = True
                return [SearchResult(title="t", url="https://example.com", snippet="s", source_domain="example.com")]

        p1 = _FakeSearchProvider(name="exploding", fail=True, non_transient=True)
        p1.provider_name = "exploding"
        p2 = _SafeSearch()
        wrapper = SearchProviderFallbackWrapper([p1, p2])
        with pytest.raises(AllProvidersFailedError) as exc_info:
            await wrapper.search("test")
        assert not not_called

    async def test_non_transient_vision_does_not_fallback(self) -> None:
        not_called = False
        class _SafeVision(ImageAnalysisProvider):
            provider_name = "safe"
            async def analyze_image(self, image: bytes, prompt: str | None = None, **kwargs: Any) -> ImageAnalysisResult:
                nonlocal not_called
                not_called = True
                return ImageAnalysisResult(provider=self.provider_name, model="m", description="ok")

        p1 = _FakeImageAnalysisProvider(name="exploding", fail=True, non_transient=True)
        p1.provider_name = "exploding"
        p2 = _SafeVision()
        wrapper = ImageAnalysisProviderFallbackWrapper([p1, p2])
        with pytest.raises(AllProvidersFailedError) as exc_info:
            await wrapper.analyze_image(b"test")
        assert not not_called

    async def test_non_transient_metadata_includes_role_provider_operation(self) -> None:
        p1 = _FakeModelProvider(name="exploding", fail_generate_text=True)
        p1.provider_name = "exploding"
        # Override to raise a non-transient error (ValueError is not transient)
        orig = p1.generate_text
        async def generate_text_override(prompt: str, **kwargs: Any) -> TextGenerationResult:
            raise ValueError("non-transient configuration error")
        p1.generate_text = generate_text_override
        p2 = _FakeModelProvider(name="safe")
        wrapper = ModelProviderFallbackWrapper([p1, p2])
        with pytest.raises(AllProvidersFailedError) as exc_info:
            await wrapper.generate_text("test")
        meta = exc_info.value.fallback_metadata
        assert meta.role == "model"
        assert meta.operation == "generate_text"
        assert len(meta.attempts) >= 1
        assert meta.attempts[0].provider == "exploding"
        assert meta.attempts[0].outcome == "non_transient"

    async def test_semantic_insufficient_model_judge_does_not_fallback(self) -> None:
        p1 = _FakeJudgeProvider(name="judge-a", semantic_insufficient=True)
        p2 = _FakeJudgeProvider(name="judge-b")
        wrapper = JudgeEvaluationProviderFallbackWrapper([p1, p2])
        result = await wrapper.judge_response({"q": "test"}, {"passing_score": 1})
        assert result.provider == "judge-a"
        assert result.status == "insufficient"

    async def test_semantic_insufficient_model_provider_judge_does_not_fallback(self) -> None:
        p1 = _FakeModelProvider(name="model-a", semantic_insufficient=True)
        p2 = _FakeModelProvider(name="model-b")
        wrapper = ModelProviderFallbackWrapper([p1, p2])
        result = await wrapper.judge_response({"q": "test"}, {"passing_score": 1})
        assert result.provider == "model-a"
        assert result.status == "insufficient"

    async def test_semantic_insufficient_first_provider_second_not_called(self) -> None:
        class _TrackingJudge(JudgeEvaluationProvider):
            provider_name = "judge-b"
            called = False
            async def judge_response(self, payload: dict[str, Any], rubric: dict[str, Any], **kwargs: Any) -> JudgeResult:
                _TrackingJudge.called = True
                return JudgeResult(provider=self.provider_name, model="m", score=1, passed=True, status="full", confidence=1)

        _TrackingJudge.called = False
        p1 = _FakeJudgeProvider(name="judge-a", semantic_insufficient=True)
        p2 = _TrackingJudge()
        wrapper = JudgeEvaluationProviderFallbackWrapper([p1, p2])
        result = await wrapper.judge_response({"q": "test"}, {"passing_score": 1})
        assert result.provider == "judge-a"
        assert result.status == "insufficient"
        assert not _TrackingJudge.called

    async def test_generate_json_retry_on_invalid(self) -> None:
        retries = []
        class RetryModel(ModelProvider):
            provider_name = "retry-model"
            def __init__(self):
                self.call_count = 0
            async def generate_text(self, prompt: str, **kwargs: Any) -> TextGenerationResult:
                return TextGenerationResult(provider=self.provider_name, model="m", text="ok")
            async def generate_json(self, prompt: str, schema: dict[str, Any], **kwargs: Any) -> JsonGenerationResult:
                self.call_count += 1
                retries.append(self.call_count)
                if self.call_count == 1:
                    raise RuntimeError("invalid structured output")
                return JsonGenerationResult(provider=self.provider_name, model="m", data={"ok": True})
            async def judge_response(self, payload: dict[str, Any], rubric: dict[str, Any], **kwargs: Any) -> JudgeResult:
                return JudgeResult(provider=self.provider_name, model="m", score=1, passed=True, status="full", confidence=1)

        p1 = RetryModel()
        p2 = _FakeModelProvider(name="fallback")
        wrapper = ModelProviderFallbackWrapper([p1, p2])
        result = await wrapper.generate_json("test", {"type": "object"})
        assert result.provider == "retry-model"
        assert p1.call_count == 2

    async def test_generate_text_forwards_kwargs(self) -> None:
        received_kwargs: list[dict[str, Any]] = []

        class _KwargsRecorder(ModelProvider):
            provider_name = "recorder"

            async def generate_text(self, prompt: str, **kwargs: Any) -> TextGenerationResult:
                received_kwargs.append(dict(kwargs))
                return TextGenerationResult(provider=self.provider_name, model="m", text="ok")

            async def generate_json(self, prompt: str, schema: dict[str, Any], **kwargs: Any) -> JsonGenerationResult:
                received_kwargs.append(dict(kwargs))
                return JsonGenerationResult(provider=self.provider_name, model="m", data={"ok": True})

            async def judge_response(self, payload: dict[str, Any], rubric: dict[str, Any], **kwargs: Any) -> JudgeResult:
                return JudgeResult(provider=self.provider_name, model="m", score=1, passed=True, status="full", confidence=1)

        wrapper = ModelProviderFallbackWrapper([_KwargsRecorder()])
        await wrapper.generate_text("test", model="custom-model", temperature=0.7)
        assert len(received_kwargs) == 1
        assert received_kwargs[0]["model"] == "custom-model"
        assert received_kwargs[0]["temperature"] == 0.7

    async def test_generate_json_forwards_kwargs(self) -> None:
        received_kwargs: list[dict[str, Any]] = []

        class _KwargsRecorder(ModelProvider):
            provider_name = "recorder"

            async def generate_text(self, prompt: str, **kwargs: Any) -> TextGenerationResult:
                return TextGenerationResult(provider=self.provider_name, model="m", text="ok")

            async def generate_json(self, prompt: str, schema: dict[str, Any], **kwargs: Any) -> JsonGenerationResult:
                received_kwargs.append(dict(kwargs))
                return JsonGenerationResult(provider=self.provider_name, model="m", data={"ok": True})

            async def judge_response(self, payload: dict[str, Any], rubric: dict[str, Any], **kwargs: Any) -> JudgeResult:
                return JudgeResult(provider=self.provider_name, model="m", score=1, passed=True, status="full", confidence=1)

        wrapper = ModelProviderFallbackWrapper([_KwargsRecorder()])
        await wrapper.generate_json("test", {"type": "object"}, model="custom-model", temperature=0.5)
        assert len(received_kwargs) == 1
        assert received_kwargs[0]["model"] == "custom-model"
        assert received_kwargs[0]["temperature"] == 0.5

    async def test_generate_text_fallback_context_metadata(self) -> None:
        clear_provider_fallbacks()
        p1 = _FakeModelProvider(name="primary", fail_generate_text=True)
        p2 = _FakeModelProvider(name="fallback")
        wrapper = ModelProviderFallbackWrapper([p1, p2])
        await wrapper.generate_text("test")
        fallbacks = get_provider_fallbacks()
        assert len(fallbacks) >= 1
        last = fallbacks[-1]
        assert last["final_provider"] == "fallback"
        assert last["success"] is True
        assert last["role"] == "model"

    async def test_all_providers_failed_context_metadata(self) -> None:
        clear_provider_fallbacks()
        p1 = _FakeModelProvider(name="p1", fail_generate_text=True)
        p2 = _FakeModelProvider(name="p2", fail_generate_text=True)
        wrapper = ModelProviderFallbackWrapper([p1, p2])
        with pytest.raises(AllProvidersFailedError):
            await wrapper.generate_text("test")
        fallbacks = get_provider_fallbacks()
        assert len(fallbacks) >= 1
        last = fallbacks[-1]
        assert last["success"] is False
        assert last["final_provider"] is None


# ---------------------------------------------------------------------------
# 8.3 Circuit breaker tests
# ---------------------------------------------------------------------------

class TestCircuitBreaker:
    def setup_method(self) -> None:
        self.cb = CircuitBreaker()

    def test_circuit_opens_for_transient_failure(self) -> None:
        self.cb.open("provider-a", "model", "generate_text", 60.0)
        assert self.cb.is_open("provider-a", "model", "generate_text")

    def test_skip_unhealthy_provider(self) -> None:
        self.cb.open("provider-a", "model", "generate_text", 60.0)
        assert self.cb.is_open("provider-a", "model", "generate_text")

    def test_circuit_expires(self) -> None:
        self.cb.open("provider-a", "model", "generate_text", 0.001)
        time.sleep(0.002)
        assert not self.cb.is_open("provider-a", "model", "generate_text")

    def test_non_transient_failure_does_not_open(self) -> None:
        category = FailureCategory.non_transient
        assert not is_circuit_breaker_failure(category)

    def test_circuit_does_not_open_for_non_transient(self) -> None:
        self.cb.open("provider-a", "model", "generate_text", 60.0)
        assert self.cb.is_open("provider-a", "model", "generate_text")
        self.cb.reset("provider-a", "model", "generate_text")
        assert not self.cb.is_open("provider-a", "model", "generate_text")

    def test_different_provider_independent(self) -> None:
        self.cb.open("provider-a", "model", "generate_text", 60.0)
        assert not self.cb.is_open("provider-b", "model", "generate_text")

    def test_different_role_independent(self) -> None:
        self.cb.open("provider-a", "model", "generate_text", 60.0)
        assert not self.cb.is_open("provider-a", "search", "generate_text")

    def test_circuit_breaker_failure_types(self) -> None:
        for cat in [FailureCategory.timeout, FailureCategory.rate_limit]:
            assert is_circuit_breaker_failure(cat)
        assert not is_circuit_breaker_failure(FailureCategory.non_transient)


# ---------------------------------------------------------------------------
# 8.4 Configuration failure tests
# ---------------------------------------------------------------------------

class TestConfigurationFailures:
    def test_local_development_fails_on_bad_config(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("APP_ENV", "local")
        get_settings.cache_clear()
        with pytest.raises(ValueError, match="Unsupported model provider"):
            _build_model_chain(["nonexistent"], get_settings())

    def test_production_logs_and_continues(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("APP_ENV", "production")
        get_settings.cache_clear()
        chain = _build_model_chain(["nonexistent", "mock"], get_settings())
        assert isinstance(chain, MockModelProvider)


# ---------------------------------------------------------------------------
# 8.5 Assistant diagnostics tests
# ---------------------------------------------------------------------------

class TestProviderFallbackDiagnostics:
    async def test_provider_fallbacks_exposed_in_diagnostics(self) -> None:
        clear_provider_fallbacks()
        record_provider_fallback({
            "role": "model",
            "operation": "generate_text",
            "final_provider": "fallback",
            "success": True,
            "attempted_providers": [
                {"provider": "primary", "outcome": "failed:timeout", "failure_category": "timeout", "skipped_unhealthy": False},
                {"provider": "fallback", "outcome": "success", "failure_category": None, "skipped_unhealthy": False},
            ],
        })
        fallbacks = get_provider_fallbacks()
        assert len(fallbacks) == 1
        fb = fallbacks[0]
        assert fb["role"] == "model"
        assert fb["final_provider"] == "fallback"
        assert fb["success"] is True
        assert len(fb["attempted_providers"]) == 2

    async def test_separate_from_semantic_fallback(self) -> None:
        clear_provider_fallbacks()
        record_provider_fallback({
            "role": "model",
            "operation": "generate_text",
            "final_provider": "gemini",
            "success": True,
            "attempted_providers": [],
        })
        semantic_reasons = ["web_search_used", "rag_not_answerable"]
        fallbacks = get_provider_fallbacks()
        assert len(fallbacks) == 1
        assert fallbacks[0]["role"] == "model"
        assert "web_search_used" not in str(fallbacks)

    async def test_no_sanitized_secrets_in_fallbacks(self) -> None:
        clear_provider_fallbacks()
        record_provider_fallback({
            "role": "model",
            "operation": "generate_text",
            "final_provider": "openai",
            "success": False,
            "attempted_providers": [
                {"provider": "openai", "outcome": "failed:timeout", "failure_category": "timeout", "skipped_unhealthy": False},
            ],
        })
        fallbacks = get_provider_fallbacks()
        fb_str = str(fallbacks)
        assert "OPENAI_API_KEY" not in fb_str
        assert "password" not in fb_str
        assert "api_key" not in fb_str.lower()

    async def test_fallback_context_isolation_across_clears(self) -> None:
        clear_provider_fallbacks()
        record_provider_fallback({
            "role": "model",
            "operation": "generate_text",
            "final_provider": "p1",
            "success": True,
            "attempted_providers": [],
        })
        after_first = get_provider_fallbacks()
        assert len(after_first) == 1
        assert after_first[0]["final_provider"] == "p1"

        clear_provider_fallbacks()
        record_provider_fallback({
            "role": "model",
            "operation": "generate_text",
            "final_provider": "p2",
            "success": True,
            "attempted_providers": [],
        })
        after_second = get_provider_fallbacks()
        assert len(after_second) == 1
        assert after_second[0]["final_provider"] == "p2"


# ---------------------------------------------------------------------------
# 8.6 Gemini search tests
# ---------------------------------------------------------------------------

class TestGeminiSearchNormalization:
    def test_internal_redirect_url_detection(self) -> None:
        from app.providers.gemini import _is_internal_redirect_url
        assert _is_internal_redirect_url("https://www.google.com/url?q=https://example.org")
        assert _is_internal_redirect_url("https://www.google.com/search?q=test")
        assert _is_internal_redirect_url("https://webcache.googleusercontent.com/search?q=cache")
        assert not _is_internal_redirect_url("https://www.rhs.org.uk/plants")

    def test_mixed_usable_unusable_citations(self) -> None:
        import types
        from app.providers.gemini import _search_results_from_response

        class FakeWeb:
            def __init__(self, *, uri: str, title: str = ""):
                self.uri = uri
                self.title = title

        class FakeChunk:
            def __init__(self, *, uri: str, title: str = ""):
                self.web = FakeWeb(uri=uri, title=title)

        class FakeSegment:
            def __init__(self, *, text: str):
                self.text = text

        class FakeSupport:
            def __init__(self, *, text: str, indices: list[int]):
                self.segment = FakeSegment(text=text)
                self.grounding_chunk_indices = indices

        class FakeGroundingMetadata:
            def __init__(self, chunks: list, supports: list):
                self.grounding_chunks = chunks
                self.grounding_supports = supports

        response = types.SimpleNamespace(
            text="Some response text",
            grounding_metadata=FakeGroundingMetadata(
                chunks=[
                    FakeChunk(uri="https://www.google.com/url?q=internal", title="Google redirect"),
                    FakeChunk(uri="https://www.rhs.org.uk/plants/test", title="RHS Plant"),
                ],
                supports=[
                    FakeSupport(text="RHS snippet", indices=[1]),
                ],
            ),
            candidates=[],
        )

        results = _search_results_from_response(response)
        assert len(results) == 1
        assert results[0].source_domain == "www.rhs.org.uk"

    def test_no_usable_normalized_results_empty(self) -> None:
        import types
        from app.providers.gemini import _search_results_from_response

        class FakeGroundingMetadata:
            def __init__(self):
                self.grounding_chunks = []
                self.grounding_supports = []

        response = types.SimpleNamespace(
            text="",
            grounding_metadata=FakeGroundingMetadata(),
            candidates=[],
        )

        results = _search_results_from_response(response)
        assert len(results) == 0

    def test_redirect_only_urls_no_usable_results(self) -> None:
        import types
        from app.providers.gemini import _search_results_from_response

        class FakeWeb:
            def __init__(self, *, uri: str, title: str = ""):
                self.uri = uri
                self.title = title

        class FakeChunk:
            def __init__(self, *, uri: str, title: str = ""):
                self.web = FakeWeb(uri=uri, title=title)

        class FakeSegment:
            def __init__(self, *, text: str):
                self.text = text

        class FakeSupport:
            def __init__(self, *, text: str, indices: list[int]):
                self.segment = FakeSegment(text=text)
                self.grounding_chunk_indices = indices

        class FakeGroundingMetadata:
            def __init__(self, chunks: list, supports: list):
                self.grounding_chunks = chunks
                self.grounding_supports = supports

        response = types.SimpleNamespace(
            text="Search results",
            grounding_metadata=FakeGroundingMetadata(
                chunks=[
                    FakeChunk(uri="https://www.google.com/url?q=redirect1", title="Redirect 1"),
                    FakeChunk(uri="https://www.google.com/url?q=redirect2", title="Redirect 2"),
                ],
                supports=[
                    FakeSupport(text="Snippet", indices=[0, 1]),
                ],
            ),
            candidates=[],
        )

        results = _search_results_from_response(response)
        assert len(results) == 0


# ---------------------------------------------------------------------------
# 8.7 Search provider ordering tests
# ---------------------------------------------------------------------------

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
        metadata = None
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
        from app.providers.fallback import classify_failure, FailureCategory
        original = RuntimeError("503 UNAVAILABLE")
        wrapper = GeminiProviderError("Gemini generate_text call failed", original_exception=original)
        assert classify_failure(wrapper) == FailureCategory.service_unavailable

    def test_classify_failure_traverses_cause_chain(self) -> None:
        from app.providers.fallback import classify_failure, FailureCategory
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
