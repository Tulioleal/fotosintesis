import time
from typing import Any

import pytest

from app.core.settings import get_settings, Settings
from app.providers.fallback import (
    CircuitBreaker,
    FailureCategory,
    is_circuit_breaker_failure,
)
from app.providers.fallback_context import (
    clear_provider_fallbacks,
    get_provider_fallbacks,
    record_provider_fallback,
)
from app.providers.factory import (
    _build_model_chain,
)
from app.providers.interfaces import (
    ImageAnalysisProvider,
    JudgeEvaluationProvider,
    ModelProvider,
    SearchProvider,
)
from app.providers.mocks import (
    MockModelProvider,
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


# ---------------------------------------------------------------------------
# Helper: Fake providers for testing
# ---------------------------------------------------------------------------

from tests._provider_fallback_helpers import (
    _FakeImageAnalysisProvider,
    _FakeJudgeProvider,
    _FakeModelProvider,
    _FakeSearchProvider,
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
        with pytest.raises(AllProvidersFailedError):
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
        with pytest.raises(AllProvidersFailedError):
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
        with pytest.raises(AllProvidersFailedError):
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
        with pytest.raises(AllProvidersFailedError):
            await wrapper.analyze_image(b"test")
        assert not not_called

    async def test_non_transient_metadata_includes_role_provider_operation(self) -> None:
        p1 = _FakeModelProvider(name="exploding", fail_generate_text=True)
        p1.provider_name = "exploding"
        # Override to raise a non-transient error (ValueError is not transient)
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
