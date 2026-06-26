"""Fallback wrapper for the judge capability."""

from __future__ import annotations

from typing import Any

from app.providers.fallback import (
    classify_failure,
    is_transient_failure,
)
from app.providers.interfaces import JudgeEvaluationProvider
from app.providers.types import JudgeResult
from app.providers.wrappers.runner import run_provider_chain


class JudgeEvaluationProviderFallbackWrapper(JudgeEvaluationProvider):
    def __init__(
        self,
        providers: list[JudgeEvaluationProvider],
        *,
        role: str = "judge",
        attempt_timeout: float | None = None,
        circuit_breaker_duration: float | None = None,
    ) -> None:
        self._providers = providers
        self._role = role
        self._attempt_timeout = attempt_timeout
        self._circuit_breaker_duration = circuit_breaker_duration

    async def judge_response(
        self, payload: dict[str, Any], rubric: dict[str, Any], **kwargs: Any
    ) -> JudgeResult:
        async def _call(p: JudgeEvaluationProvider) -> JudgeResult:
            try:
                return await p.judge_response(payload, rubric, **kwargs)
            except Exception as exc:
                category = classify_failure(exc)
                if not is_transient_failure(category):
                    raise
                if category.value not in ("invalid_structured_output", "empty_response"):
                    raise
                return await p.judge_response(payload, rubric, **kwargs)

        return await run_provider_chain(
            providers=self._providers,
            operation="judge_response",
            role=self._role,
            call=_call,
            attempt_timeout=self._attempt_timeout,
            circuit_breaker_duration=self._circuit_breaker_duration,
        )
