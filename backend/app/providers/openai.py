import base64
import json
from collections.abc import Awaitable, Callable
from typing import Any

from app.observability.provider_logging import log_provider_call
from app.providers.interfaces import ImageAnalysisProvider, JudgeEvaluationProvider, ModelProvider
from app.providers.types import (
    ConfidenceLabel,
    ImageAnalysisResult,
    JudgeResult,
    JsonGenerationResult,
    PlantCandidate,
    TextGenerationResult,
)


class OpenAIProviderError(RuntimeError):
    pass


def _client(api_key: str) -> Any:
    try:
        from openai import AsyncOpenAI
    except ImportError as exc:
        raise OpenAIProviderError("The openai package is required for OpenAI providers") from exc
    return AsyncOpenAI(api_key=api_key)


def _response_text(response: Any) -> str:
    text = getattr(response, "output_text", None)
    if isinstance(text, str):
        return text
    raise OpenAIProviderError("OpenAI response did not include output_text")


def _json_from_response(response: Any) -> dict[str, Any]:
    text = _response_text(response)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise OpenAIProviderError("OpenAI response was not valid JSON") from exc
    if not isinstance(data, dict):
        raise OpenAIProviderError("OpenAI JSON response must be an object")
    return data


async def _logged(
    *,
    provider: str,
    role: str,
    operation: str,
    call: Callable[[], Awaitable[Any]],
) -> Any:
    return await log_provider_call(provider, operation, call, role=role)


class OpenAIModelProvider(ModelProvider):
    provider_name = "openai-model"

    def __init__(self, *, api_key: str, model: str) -> None:
        self.model = model
        self._client = _client(api_key)

    async def generate_text(self, prompt: str, **kwargs: Any) -> TextGenerationResult:
        response = await _logged(
            provider=self.provider_name,
            role="model",
            operation="generate_text",
            call=lambda: self._client.responses.create(
                model=kwargs.pop("model", self.model),
                input=prompt,
                **kwargs,
            ),
        )
        return TextGenerationResult(
            provider=self.provider_name,
            model=self.model,
            text=_response_text(response),
        )

    async def generate_json(
        self, prompt: str, schema: dict[str, Any], **kwargs: Any
    ) -> JsonGenerationResult:
        response = await _logged(
            provider=self.provider_name,
            role="model",
            operation="generate_json",
            call=lambda: self._client.responses.create(
                model=kwargs.pop("model", self.model),
                input=prompt,
                text={"format": {"type": "json_object"}},
                **kwargs,
            ),
        )
        return JsonGenerationResult(
            provider=self.provider_name,
            model=self.model,
            data=_json_from_response(response),
            metadata={"schema_keys": sorted(schema.keys())},
        )

    async def judge_response(
        self, payload: dict[str, Any], rubric: dict[str, Any], **kwargs: Any
    ) -> JudgeResult:
        judge = OpenAIJudgeProvider(api_key="", model=self.model, client=self._client)
        return await judge.judge_response(payload, rubric, **kwargs)


class OpenAIVisionProvider(ImageAnalysisProvider):
    provider_name = "openai-vision"

    def __init__(self, *, api_key: str, model: str) -> None:
        self.model = model
        self._client = _client(api_key)

    async def analyze_image(
        self, image: bytes, prompt: str | None = None, **kwargs: Any
    ) -> ImageAnalysisResult:
        mime_type = kwargs.pop("mime_type", "image/jpeg")
        model = kwargs.pop("model", self.model)
        image_url = f"data:{mime_type};base64,{base64.b64encode(image).decode('ascii')}"
        prompt_text = _vision_prompt(prompt)
        response = await _logged(
            provider=self.provider_name,
            role="vision",
            operation="analyze_image",
            call=lambda: self._client.responses.create(
                model=model,
                input=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "input_text",
                                "text": prompt_text,
                            },
                            {"type": "input_image", "image_url": image_url},
                        ],
                    }
                ],
                text={"format": {"type": "json_object"}},
                **kwargs,
            ),
        )
        data = _json_from_response(response)
        candidates = [
            PlantCandidate(
                scientific_name=str(candidate.get("scientific_name") or "Unknown plant"),
                common_name=candidate.get("common_name"),
                confidence_label=_confidence_label(candidate.get("confidence_label")),
                confidence_score=candidate.get("confidence_score"),
                visible_traits=list(candidate.get("visible_traits") or []),
                provider=self.provider_name,
            )
            for candidate in data.get("candidates", [])
            if isinstance(candidate, dict)
        ]
        return ImageAnalysisResult(
            provider=self.provider_name,
            model=self.model,
            description=str(data.get("description") or _response_text(response)),
            candidates=candidates,
            metadata={"image_size_bytes": len(image)},
        )


class OpenAIJudgeProvider(JudgeEvaluationProvider):
    provider_name = "openai-judge"

    def __init__(self, *, api_key: str, model: str, client: Any | None = None) -> None:
        self.model = model
        self._client = client or _client(api_key)

    async def judge_response(
        self, payload: dict[str, Any], rubric: dict[str, Any], **kwargs: Any
    ) -> JudgeResult:
        response = await _logged(
            provider=self.provider_name,
            role="judge",
            operation="judge_response",
            call=lambda: self._client.responses.create(
                model=kwargs.pop("model", self.model),
                input=_judge_prompt(payload, rubric),
                text={"format": {"type": "json_object"}},
                **kwargs,
            ),
        )
        data = _json_from_response(response)
        score = float(data.get("score", 0))
        passed = bool(data.get("passed", score >= float(rubric.get("passing_score", 1))))
        reasons = data.get("reasons") or []
        return JudgeResult(
            provider=self.provider_name,
            model=self.model,
            score=score,
            passed=passed,
            reasons=[str(reason) for reason in reasons],
        )


def _confidence_label(value: Any) -> ConfidenceLabel:
    try:
        return ConfidenceLabel(str(value))
    except ValueError:
        return ConfidenceLabel.inconclusive


def _judge_prompt(payload: dict[str, Any], rubric: dict[str, Any]) -> str:
    return (
        "Evaluate the assistant output against the rubric. "
        "Return JSON with score, passed, and reasons.\n"
        f"Payload:\n{json.dumps(payload, ensure_ascii=True, sort_keys=True)}\n"
        f"Rubric:\n{json.dumps(rubric, ensure_ascii=True, sort_keys=True)}"
    )


def _vision_prompt(prompt: str | None) -> str:
    base_prompt = prompt.strip() if prompt else _VISION_PROMPT
    return (
        f"{base_prompt}\n"
        "Return only valid JSON with this structure: "
        "{\"description\": string, \"candidates\": ["
        "{\"scientific_name\": string, \"common_name\": string | null, "
        "\"confidence_label\": \"high\" | \"medium\" | \"low\" | \"inconclusive\", "
        "\"confidence_score\": number | null, \"visible_traits\": string[]}]}"
    )


_VISION_PROMPT = """
Analyze this plant image. Return JSON with description and candidates. Each candidate must include
scientific_name, common_name, confidence_label, confidence_score and visible_traits.
""".strip()
