"""OpenAI model provider (text and JSON generation)."""

from __future__ import annotations

from typing import Any

from app.providers.interfaces import ModelProvider
from app.providers.openai._client import (
    json_from_response,
    logged_call,
    openai_client,
    response_text,
)
from app.providers.openai.judge import OpenAIJudgeProvider
from app.providers.openai.strict_format import build_strict_text_format
from app.providers.types import JsonGenerationResult, JudgeResult, TextGenerationResult


class OpenAIModelProvider(ModelProvider):
    provider_name = "openai-model"

    def __init__(
        self, *, api_key: str, model: str, classifier_model: str | None = None
    ) -> None:
        self.model = model
        self.classifier_model = classifier_model or model
        self._client = openai_client(api_key)

    def _resolve_model(self, kwargs: dict[str, Any]) -> str:
        explicit = kwargs.pop("model", None)
        if explicit is not None:
            return explicit
        purpose = kwargs.pop("model_purpose", None)
        if purpose == "classifier":
            return self.classifier_model
        return self.model

    async def generate_text(self, prompt: str, **kwargs: Any) -> TextGenerationResult:
        selected_model = self._resolve_model(kwargs)
        response = await logged_call(
            provider=self.provider_name,
            role="model",
            operation="generate_text",
            call=lambda: self._client.responses.create(
                model=selected_model,
                input=prompt,
                **kwargs,
            ),
        )
        return TextGenerationResult(
            provider=self.provider_name,
            model=selected_model,
            text=response_text(response),
        )

    async def generate_json(
        self, prompt: str, schema: dict[str, Any], **kwargs: Any
    ) -> JsonGenerationResult:
        selected_model = self._resolve_model(kwargs)
        text_format = build_strict_text_format(
            schema=schema,
            name="care_classifier",
            provider=self.provider_name,
            role="model",
            operation="generate_json",
        )
        if text_format is None:
            text_format = {"format": {"type": "json_object"}}
        else:
            text_format = {"format": text_format}
        response = await logged_call(
            provider=self.provider_name,
            role="model",
            operation="generate_json",
            call=lambda: self._client.responses.create(
                model=selected_model,
                input=prompt,
                text=text_format,
                **kwargs,
            ),
        )
        return JsonGenerationResult(
            provider=self.provider_name,
            model=selected_model,
            data=json_from_response(response),
            metadata={"schema_keys": sorted(schema.keys())},
        )

    async def judge_response(
        self, payload: dict[str, Any], rubric: dict[str, Any], **kwargs: Any
    ) -> JudgeResult:
        judge = OpenAIJudgeProvider(api_key="", model=self.model, client=self._client)
        return await judge.judge_response(payload, rubric, **kwargs)
