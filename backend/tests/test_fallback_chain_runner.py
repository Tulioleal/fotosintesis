"""Tests for the shared provider fallback chain runner."""

from __future__ import annotations

from typing import Any

import pytest

from app.providers.fallback_context import clear_provider_fallbacks, get_provider_fallbacks
from app.providers.types import TextGenerationResult
from app.providers.wrappers.exceptions import AllProvidersFailedError
from app.providers.wrappers.runner import run_provider_chain


class _FakeProvider:
    def __init__(self, name: str, *, result: TextGenerationResult | None = None,
                 raises: Exception | None = None, empty: bool = False) -> None:
        self.provider_name = name
        self._result = result
        self._raises = raises
        self._empty = empty
        self.calls = 0

    async def generate_text(self, prompt: str, **kwargs: Any) -> TextGenerationResult:
        self.calls += 1
        if self._raises is not None:
            raise self._raises
        if self._empty:
            return TextGenerationResult(provider=self.provider_name, model="m", text="")
        assert self._result is not None
        return self._result


def _fallback_unusable_hook(
    result: Any, provider: str, index: int
) -> Exception | None:
    if not getattr(result, "text", ""):
        return ValueError(f"{provider} produced no usable text")
    return None


@pytest.fixture(autouse=True)
def _reset_fallbacks() -> None:
    clear_provider_fallbacks()


@pytest.mark.asyncio
async def test_run_provider_chain_returns_first_success() -> None:
    p1 = _FakeProvider("p1", raises=ConnectionError("network down"))
    p2 = _FakeProvider(
        "p2",
        result=TextGenerationResult(provider="p2", model="m", text="ok"),
    )
    result = await run_provider_chain(
        providers=[p1, p2],
        operation="generate_text",
        role="model",
        call=lambda p: p.generate_text("hi"),
    )
    assert result.text == "ok"
    assert p1.calls == 1
    assert p2.calls == 1


@pytest.mark.asyncio
async def test_run_provider_chain_raises_all_failed_when_no_provider_succeeds() -> None:
    p1 = _FakeProvider("p1", raises=ConnectionError("network down"))
    p2 = _FakeProvider("p2", raises=ConnectionError("network down"))
    with pytest.raises(AllProvidersFailedError) as exc_info:
        await run_provider_chain(
            providers=[p1, p2],
            operation="generate_text",
            role="model",
            call=lambda p: p.generate_text("hi"),
        )
    metadata = exc_info.value.fallback_metadata
    assert metadata.success is False
    assert metadata.role == "model"
    assert metadata.operation == "generate_text"
    assert [a.provider for a in metadata.attempts] == ["p1", "p2"]
    fallbacks = get_provider_fallbacks()
    assert len(fallbacks) == 1
    assert fallbacks[0]["success"] is False


@pytest.mark.asyncio
async def test_run_provider_chain_records_fallback_on_success() -> None:
    p1 = _FakeProvider("p1", raises=ConnectionError("network down"))
    p2 = _FakeProvider(
        "p2",
        result=TextGenerationResult(provider="p2", model="m", text="ok"),
    )
    await run_provider_chain(
        providers=[p1, p2],
        operation="generate_text",
        role="model",
        call=lambda p: p.generate_text("hi"),
    )
    fallbacks = get_provider_fallbacks()
    assert len(fallbacks) == 1
    assert fallbacks[0]["success"] is True
    assert fallbacks[0]["final_provider"] == "p2"
    assert len(fallbacks[0]["attempted_providers"]) == 2


@pytest.mark.asyncio
async def test_run_provider_chain_unusable_hook_marks_attempt_failed() -> None:
    p1 = _FakeProvider("p1", empty=True)
    p2 = _FakeProvider(
        "p2",
        result=TextGenerationResult(provider="p2", model="m", text="ok"),
    )
    result = await run_provider_chain(
        providers=[p1, p2],
        operation="generate_text",
        role="model",
        call=lambda p: p.generate_text("hi"),
        unusable_result_hook=_fallback_unusable_hook,
    )
    assert result.text == "ok"
    fallbacks = get_provider_fallbacks()
    assert fallbacks[0]["final_provider"] == "p2"


@pytest.mark.asyncio
async def test_run_provider_chain_unusable_hook_only_records_attempts_when_all_unusable() -> None:
    p1 = _FakeProvider("p1", empty=True)
    p2 = _FakeProvider("p2", empty=True)
    with pytest.raises(AllProvidersFailedError):
        await run_provider_chain(
            providers=[p1, p2],
            operation="generate_text",
            role="model",
            call=lambda p: p.generate_text("hi"),
            unusable_result_hook=_fallback_unusable_hook,
        )
    fallbacks = get_provider_fallbacks()
    assert fallbacks[0]["success"] is False
    attempts = fallbacks[0]["attempted_providers"]
    assert len(attempts) == 2
    assert {a["provider"] for a in attempts} == {"p1", "p2"}
    assert all("failed:unusable_search_output" in a["outcome"] for a in attempts)


@pytest.mark.asyncio
async def test_run_provider_chain_skips_circuit_open_providers() -> None:
    from app.providers.fallback import circuit_breaker

    p1 = _FakeProvider("p1", raises=TimeoutError("timed out"))
    p2 = _FakeProvider(
        "p2",
        result=TextGenerationResult(provider="p2", model="m", text="ok"),
    )
    circuit_breaker.open("p1", "model", "generate_text", 60.0)
    try:
        result = await run_provider_chain(
            providers=[p1, p2],
            operation="generate_text",
            role="model",
            call=lambda p: p.generate_text("hi"),
        )
        assert result.text == "ok"
        assert p1.calls == 0
    finally:
        circuit_breaker.clear()
