"""OpenAI judge provider."""

from __future__ import annotations

import json
from typing import Any

from app.providers.interfaces import JudgeEvaluationProvider
from app.providers.openai._client import (
    json_from_response,
    logged_call,
    openai_client,
)
from app.providers.openai.response_schemas import rubric_judge_schema
from app.providers.openai.strict_format import build_strict_text_format
from app.providers.types import JudgeResult


def _judge_prompt(payload: dict[str, Any], rubric: dict[str, Any]) -> str:
    return (
        "Evaluate the assistant output against the rubric. "
        "Return only valid JSON matching the rubric's expected_output.\n"
        f"Payload:\n{json.dumps(payload, ensure_ascii=True, sort_keys=True)}\n"
        f"Rubric:\n{json.dumps(rubric, ensure_ascii=True, sort_keys=True)}"
    )


class OpenAIJudgeProvider(JudgeEvaluationProvider):
    provider_name = "openai-judge"

    def __init__(self, *, api_key: str, model: str, client: Any | None = None) -> None:
        self.model = model
        self._client = client or openai_client(api_key)

    async def judge_response(
        self, payload: dict[str, Any], rubric: dict[str, Any], **kwargs: Any
    ) -> JudgeResult:
        strict_schema = rubric_judge_schema(rubric)
        text_format = build_strict_text_format(
            schema=strict_schema,
            name="judge_response",
            provider=self.provider_name,
            role="judge",
            operation="judge_response",
        )
        text_kwargs = (
            {"format": text_format} if text_format is not None else {"format": {"type": "json_object"}}
        )
        response = await logged_call(
            provider=self.provider_name,
            role="judge",
            operation="judge_response",
            call=lambda: self._client.responses.create(
                model=kwargs.pop("model", self.model),
                input=_judge_prompt(payload, rubric),
                text=text_kwargs,
                **kwargs,
            ),
        )
        data = json_from_response(response)
        return JudgeResult.from_provider_data(
            provider=self.provider_name,
            model=self.model,
            data=data,
            passing_score=float(rubric.get("passing_score", 1)),
        )
