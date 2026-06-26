"""Gemini judge provider."""

from __future__ import annotations

import json
from typing import Any

from app.providers.gemini._client import (
    generate_content,
    gemini_client,
    json_from_response,
    logged_call,
)
from app.providers.gemini.configs import json_generation_config
from app.providers.gemini.response_schemas import JUDGE_SCHEMA
from app.providers.interfaces import JudgeEvaluationProvider
from app.providers.types import JudgeResult


def _judge_prompt(payload: dict[str, Any], rubric: dict[str, Any]) -> str:
    return (
        "Evaluate the assistant output against the rubric. "
        "Return only valid JSON matching the rubric's expected_output.\n"
        f"Payload:\n{json.dumps(payload, ensure_ascii=True, sort_keys=True)}\n"
        f"Rubric:\n{json.dumps(rubric, ensure_ascii=True, sort_keys=True)}"
    )


class GeminiJudgeProvider(JudgeEvaluationProvider):
    provider_name = "gemini-judge"

    def __init__(self, *, api_key: str, model: str, client: Any | None = None) -> None:
        self.model = model
        self._client = client or gemini_client(api_key)

    async def judge_response(
        self, payload: dict[str, Any], rubric: dict[str, Any], **kwargs: Any
    ) -> JudgeResult:
        model = kwargs.pop("model", self.model)
        response = await logged_call(
            provider=self.provider_name,
            role="judge",
            operation="judge_response",
            call=lambda: generate_content(
                self._client,
                model=model,
                contents=_judge_prompt(payload, rubric),
                config=json_generation_config(schema=JUDGE_SCHEMA, **kwargs),
            ),
        )
        data = json_from_response(response)
        return JudgeResult.from_provider_data(
            provider=self.provider_name,
            model=model,
            data=data,
            passing_score=float(rubric.get("passing_score", 1)),
        )
