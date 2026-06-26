"""Shared provider failure exception types.

Centralizes simple provider exception hierarchies so provider adapters
and consumer code can exchange failures without coupling to a specific
provider module. The complex ``AllProvidersFailedError`` is kept in
``app.providers.wrappers`` because it is bound to the wrapper's
``ProviderFallbackMetadata`` type.
"""

from __future__ import annotations


class ProviderError(RuntimeError):
    """Base class for all provider-level errors."""


class OpenAIProviderError(ProviderError):
    pass


class GeminiProviderError(ProviderError):
    def __init__(self, message: str, *, original_exception: Exception | None = None) -> None:
        super().__init__(message)
        self.original_exception = original_exception


class PlantDataProviderError(ProviderError):
    pass


__all__ = [
    "ProviderError",
    "OpenAIProviderError",
    "GeminiProviderError",
    "PlantDataProviderError",
]
