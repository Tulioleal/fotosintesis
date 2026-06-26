"""Gemini model provider (text and JSON generation)."""

from __future__ import annotations

from typing import Any

from app.providers.gemini._client import (
    generate_content,
    gemini_client,
    json_from_response,
    logged_call,
    response_text,
)
from app.providers.gemini.configs import (
    generation_config,
    json_generation_config,
)
from app.providers.gemini.judge import GeminiJudgeProvider
from app.providers.interfaces import ModelProvider
from app.providers.types import JsonGenerationResult, JudgeResult, TextGenerationResult


class GeminiModelProvider(ModelProvider):
    provider_name = "gemini-model"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        classifier_model: str | None = None,
        client: Any | None = None,
    ) -> None:
        self.model = model
        self.classifier_model = classifier_model or model
        self._client = client or gemini_client(api_key)

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
            call=lambda: generate_content(
                self._client,
                model=selected_model,
                contents=prompt,
                config=generation_config(**kwargs),
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
        response = await logged_call(
            provider=self.provider_name,
            role="model",
            operation="generate_json",
            call=lambda: generate_content(
                self._client,
                model=selected_model,
                contents=prompt,
                config=json_generation_config(schema=schema, **kwargs),
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
        judge = GeminiJudgeProvider(api_key="", model=self.model, client=self._client)
        return await judge.judge_response(payload, rubric, **kwargs)
