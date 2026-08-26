"""Build a ProviderRegistry with providers wrapped for recording or replay."""

from __future__ import annotations

from typing import Any

from app.evaluation.recordings import (
    RecordEmbeddingProvider,
    RecordJudgeEvaluationProvider,
    RecordModelProvider,
    RecordPlantDataProvider,
    RecordSearchProvider,
    RecordingMode,
    RecordingStore,
    ReplayEmbeddingProvider,
    ReplayJudgeEvaluationProvider,
    ReplayModelProvider,
    ReplayPlantDataProvider,
    ReplaySearchProvider,
)
from app.providers.factory import ProviderRegistry


class RecordingProviderRegistry:
    """Return a normal ``ProviderRegistry`` whose providers are wrapped per
    the selected recording mode.

    In record mode providers forward to the real providers and store
    responses. In replay mode providers return recorded responses and raise
    explicit errors on a miss or mismatch. Live and reference modes pass the
    base registry through untouched.
    """

    def __init__(
        self,
        *,
        mode: RecordingMode | None,
        store: RecordingStore | None = None,
        provider_identity: dict[str, str] | None = None,
    ) -> None:
        self.mode = mode
        self.store = store
        self.provider_identity = provider_identity or {}

    def _wrap_model(self, registry: ProviderRegistry, store: RecordingStore) -> Any:
        if self.mode == RecordingMode.replay:
            return ReplayModelProvider(
                store, role="model", provider=self.provider_identity.get("model", "model"), model=None
            )
        return RecordModelProvider(
            registry.model, store, role="model", provider=self.provider_identity.get("model", "model"), model=None
        )

    def build(self, registry: ProviderRegistry) -> ProviderRegistry:
        if self.mode is None:
            return registry
        assert self.store is not None
        store = self.store
        return ProviderRegistry(
            model=self._wrap_model(registry, store),
            vision=registry.vision,
            judge=self._wrap_judge(registry, store),
            search=self._wrap_search(registry, store),
            embeddings=self._wrap_embeddings(registry, store),
            trefle=self._wrap_plant(registry, store, "trefle"),
            perenual=self._wrap_plant(registry, store, "perenual"),
        )

    def _wrap_judge(self, registry: ProviderRegistry, store: RecordingStore) -> Any:
        provider = self.provider_identity.get("judge", "judge")
        if self.mode == RecordingMode.replay:
            return ReplayJudgeEvaluationProvider(store, provider=provider, model=None)
        return RecordJudgeEvaluationProvider(registry.judge, store, provider=provider, model=None)

    def _wrap_search(self, registry: ProviderRegistry, store: RecordingStore) -> Any:
        provider = self.provider_identity.get("search", "search")
        if self.mode == RecordingMode.replay:
            return ReplaySearchProvider(store, provider=provider)
        return RecordSearchProvider(registry.search, store, provider=provider)

    def _wrap_embeddings(self, registry: ProviderRegistry, store: RecordingStore) -> Any:
        provider = self.provider_identity.get("embeddings", "embeddings")
        if self.mode == RecordingMode.replay:
            return ReplayEmbeddingProvider(store, provider=provider, model=None)
        return RecordEmbeddingProvider(registry.embeddings, store, provider=provider, model=None)

    def _wrap_plant(self, registry: ProviderRegistry, store: RecordingStore, name: str) -> Any:
        inner = registry.trefle if name == "trefle" else registry.perenual
        provider = self.provider_identity.get(name, name)
        if self.mode == RecordingMode.replay:
            return ReplayPlantDataProvider(store, provider=provider)
        return RecordPlantDataProvider(inner, store, provider=provider)


__all__ = ["RecordingProviderRegistry"]
