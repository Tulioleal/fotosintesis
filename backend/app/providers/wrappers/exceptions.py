"""Exceptions raised by provider fallback wrappers."""

from __future__ import annotations

from app.providers.fallback import ProviderFallbackMetadata


class AllProvidersFailedError(RuntimeError):
    def __init__(self, metadata: ProviderFallbackMetadata) -> None:
        self.fallback_metadata = metadata
        super().__init__(
            f"All providers failed for role={metadata.role} operation={metadata.operation}"
        )

    @property
    def is_transient(self) -> bool:
        return any(a.transient for a in self.fallback_metadata.attempts if a.failure_category)

    @property
    def is_retryable(self) -> bool:
        return self.is_transient


class _NonTransientProviderError(AllProvidersFailedError):
    pass


class _UnusableSearchOutputError(Exception):
    pass


class _ProviderAttemptError(Exception):
    """Wraps an exception from the chain runner to carry elapsed latency."""

    def __init__(self, original_exception: Exception, latency_seconds: float) -> None:
        self.original_exception = original_exception
        self.latency_seconds = latency_seconds
        super().__init__(str(original_exception))


__all__ = [
    "AllProvidersFailedError",
    "_NonTransientProviderError",
    "_ProviderAttemptError",
    "_UnusableSearchOutputError",
]
