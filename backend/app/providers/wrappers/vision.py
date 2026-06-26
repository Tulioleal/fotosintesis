"""Fallback wrapper for the image analysis (vision) capability."""

from __future__ import annotations

from typing import Any

from app.providers.interfaces import ImageAnalysisProvider
from app.providers.types import ImageAnalysisResult
from app.providers.wrappers.runner import run_provider_chain


class ImageAnalysisProviderFallbackWrapper(ImageAnalysisProvider):
    def __init__(
        self,
        providers: list[ImageAnalysisProvider],
        *,
        role: str = "vision",
        attempt_timeout: float | None = None,
        circuit_breaker_duration: float | None = None,
    ) -> None:
        self._providers = providers
        self._role = role
        self._attempt_timeout = attempt_timeout
        self._circuit_breaker_duration = circuit_breaker_duration

    async def analyze_image(
        self, image: bytes, prompt: str | None = None, **kwargs: Any
    ) -> ImageAnalysisResult:
        return await run_provider_chain(
            providers=self._providers,
            operation="analyze_image",
            role=self._role,
            call=lambda p: p.analyze_image(image, prompt, **kwargs),
            attempt_timeout=self._attempt_timeout,
            circuit_breaker_duration=self._circuit_breaker_duration,
        )
