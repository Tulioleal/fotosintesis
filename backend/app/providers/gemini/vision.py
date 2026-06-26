"""Gemini vision provider (plant image analysis)."""

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
    image_contents,
    json_generation_config,
)
from app.providers.gemini.response_schemas import VISION_PROMPT, VISION_SCHEMA
from app.providers.interfaces import ImageAnalysisProvider
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
        '"confidence_score": number | null, "visible_traits": string[]}]} '
        "Return at most three candidates."
    )


class GeminiVisionProvider(ImageAnalysisProvider):
    provider_name = "gemini-vision"

    def __init__(self, *, api_key: str, model: str, client: Any | None = None) -> None:
        self.model = model
        self._client = client or gemini_client(api_key)

    async def analyze_image(
        self, image: bytes, prompt: str | None = None, **kwargs: Any
    ) -> ImageAnalysisResult:
        mime_type = kwargs.pop("mime_type", "image/jpeg")
        model = kwargs.pop("model", self.model)
        prompt_text = _vision_prompt(prompt)
        response = await logged_call(
            provider=self.provider_name,
            role="vision",
            operation="analyze_image",
            call=lambda: generate_content(
                self._client,
                model=model,
                contents=image_contents(prompt_text, image, mime_type),
                config=json_generation_config(schema=VISION_SCHEMA, **kwargs),
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
        ][:3]
        return ImageAnalysisResult(
            provider=self.provider_name,
            model=model,
            description=str(data.get("description") or response_text(response)),
            candidates=candidates,
            metadata={"image_size_bytes": len(image)},
        )
