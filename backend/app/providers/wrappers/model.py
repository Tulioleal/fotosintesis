"""Fallback wrappers for the model provider capability."""

from __future__ import annotations

from typing import Any

from app.providers.fallback import (
    classify_failure,
    is_transient_failure,
)
from app.providers.interfaces import ModelProvider
from app.providers.types import JsonGenerationResult, JudgeResult, TextGenerationResult
from app.providers.wrappers.runner import run_provider_chain


class ModelProviderFallbackWrapper(ModelProvider):
    def __init__(
        self,
        providers: list[ModelProvider],
        *,
        role: str = "model",
        attempt_timeout: float | None = None,
        circuit_breaker_duration: float | None = None,
    ) -> None:
        self._providers = providers
        self._role = role
        self._attempt_timeout = attempt_timeout
        self._circuit_breaker_duration = circuit_breaker_duration

    async def generate_text(self, prompt: str, **kwargs: Any) -> TextGenerationResult:
        return await run_provider_chain(
            providers=self._providers,
            operation="generate_text",
            role=self._role,
            call=lambda p: p.generate_text(prompt, **kwargs),
            attempt_timeout=self._attempt_timeout,
            circuit_breaker_duration=self._circuit_breaker_duration,
        )

    async def generate_json(
        self, prompt: str, schema: dict[str, Any], **kwargs: Any
    ) -> JsonGenerationResult:
        async def _call(p: ModelProvider) -> JsonGenerationResult:
            try:
                return await p.generate_json(prompt, schema, **kwargs)
            except Exception as exc:
                category = classify_failure(exc)
                if not is_transient_failure(category):
                    raise
                if category.value not in ("invalid_structured_output", "empty_response"):
                    raise
                # retry once for structured output failures
                return await p.generate_json(prompt, schema, **kwargs)

        return await run_provider_chain(
            providers=self._providers,
            operation="generate_json",
            role=self._role,
            call=_call,
            attempt_timeout=self._attempt_timeout,
            circuit_breaker_duration=self._circuit_breaker_duration,
        )

    async def judge_response(
        self, payload: dict[str, Any], rubric: dict[str, Any], **kwargs: Any
    ) -> JudgeResult:
        return await run_provider_chain(
            providers=self._providers,
            operation="judge_response",
            role=self._role,
            call=lambda p: p.judge_response(payload, rubric, **kwargs),
            attempt_timeout=self._attempt_timeout,
            circuit_breaker_duration=self._circuit_breaker_duration,
        )
