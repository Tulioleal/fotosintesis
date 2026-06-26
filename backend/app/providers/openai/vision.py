"""OpenAI vision provider (plant image analysis)."""

from __future__ import annotations

import base64
from typing import Any

from app.providers.interfaces import ImageAnalysisProvider
from app.providers.openai._client import (
    json_from_response,
    logged_call,
    openai_client,
    response_text,
)
from app.providers.openai.response_schemas import VISION_PROMPT, VISION_SCHEMA
from app.providers.openai.strict_format import build_strict_text_format
from app.providers.types import ConfidenceLabel, ImageAnalysisResult, PlantCandidate


def _confidence_label(value: Any) -> ConfidenceLabel:
    try:
        return ConfidenceLabel(str(value))
    except ValueError:
        return ConfidenceLabel.inconclusive


def _vision_prompt(prompt: str | None) -> str:
    base_prompt = prompt.strip() if prompt else VISION_PROMPT
    return (
        f"{base_prompt}\n"
        "Return only valid JSON with this structure: "
        '{"description": string, "candidates": ['
        '{"scientific_name": string, "common_name": string | null, '
        '"confidence_label": "high" | "medium" | "low" | "inconclusive", '
        '"confidence_score": number | null, "visible_traits": string[]}]}'
    )


class OpenAIVisionProvider(ImageAnalysisProvider):
    provider_name = "openai-vision"

    def __init__(self, *, api_key: str, model: str) -> None:
        self.model = model
        self._client = openai_client(api_key)

    async def analyze_image(
        self, image: bytes, prompt: str | None = None, **kwargs: Any
    ) -> ImageAnalysisResult:
        mime_type = kwargs.pop("mime_type", "image/jpeg")
        model = kwargs.pop("model", self.model)
        image_url = f"data:{mime_type};base64,{base64.b64encode(image).decode('ascii')}"
        prompt_text = _vision_prompt(prompt)
        text_format = build_strict_text_format(
            schema=VISION_SCHEMA,
            name="plant_image_analysis",
            provider=self.provider_name,
            role="vision",
            operation="analyze_image",
        )
        text_kwargs = (
            {"format": text_format} if text_format is not None else {"format": {"type": "json_object"}}
        )
        response = await logged_call(
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
                text=text_kwargs,
                **kwargs,
            ),
        )
        data = json_from_response(response)
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
            description=str(data.get("description") or response_text(response)),
            candidates=candidates,
            metadata={"image_size_bytes": len(image)},
        )
