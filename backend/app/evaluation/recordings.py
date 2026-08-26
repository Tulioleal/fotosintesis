"""Deterministic provider recording and replay for evaluation mode.

Recordings are thin adapters over the existing provider interfaces. They
replay (or record) responses at the provider boundary so the assistant
graph, repositories, retrieval, routing, and persistence execute normally
while provider responses stay deterministic.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from app.providers.interfaces import (
    EmbeddingProvider,
    JudgeEvaluationProvider,
    JsonGenerationProvider,
    PlantDataProvider,
    SearchProvider,
    TextGenerationProvider,
)
from app.providers.types import (
    EmbeddingResult,
    JudgeResult,
    JsonGenerationResult,
    PlantDataResult,
    SearchResult,
    TextGenerationResult,
)


class RecordingMode(str, Enum):
    record = "record"
    replay = "replay"


RECORDING_SCHEMA_VERSION = 1


class RecordingError(RuntimeError):
    """Base class for evaluation infrastructure recording errors."""


class RecordingMissError(RecordingError):
    """A recorded run encountered a provider call with no matching entry."""


class RecordingMismatchError(RecordingError):
    """A recording's schema version or provider identity does not match."""


@dataclass(frozen=True)
class RecordingEntry:
    key: str
    role: str
    provider: str
    model: str | None
    latency_ms: float | None
    payload: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "role": self.role,
            "provider": self.provider,
            "model": self.model,
            "latency_ms": self.latency_ms,
            "payload": self.payload,
        }


class RecordingStore:
    """A single JSON file holding versioned recording entries.

    Lookups are keyed by a deterministic request fingerprint, never
    positional, so graph routing changes fail loudly on a real mismatch.
    """

    def __init__(
        self,
        path: Path | None = None,
        *,
        expected_provider_identity: dict[str, str] | None = None,
    ) -> None:
        self.path = path
        self.expected_provider_identity = expected_provider_identity or {}
        self._entries: dict[str, RecordingEntry] = {}
        self._schema_version: int = RECORDING_SCHEMA_VERSION

    @classmethod
    def load(cls, path: Path, *, expected_provider_identity: dict[str, str] | None = None) -> "RecordingStore":
        store = cls(path, expected_provider_identity=expected_provider_identity)
        if not path.exists():
            raise RecordingMissError(f"Recording set not found: {path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        schema_version = int(data.get("schema_version", 0))
        if schema_version != RECORDING_SCHEMA_VERSION:
            raise RecordingMismatchError(
                f"Recording schema version {schema_version} does not match "
                f"current version {RECORDING_SCHEMA_VERSION}"
            )
        store._schema_version = schema_version
        recorded_identity = data.get("provider_identity", {}) or {}
        for role, provider in store.expected_provider_identity.items():
            if recorded_identity.get(role) != provider:
                raise RecordingMismatchError(
                    f"Recording provider identity mismatch for role '{role}': "
                    f"expected '{provider}', recorded '{recorded_identity.get(role)}'"
                )
        for raw in data.get("entries", []):
            entry = RecordingEntry(
                key=str(raw["key"]),
                role=str(raw["role"]),
                provider=str(raw.get("provider") or ""),
                model=raw.get("model"),
                latency_ms=raw.get("latency_ms"),
                payload=raw.get("payload", {}),
            )
            store._entries[entry.key] = entry
        return store

    def save(self, provider_identity: dict[str, str] | None = None) -> None:
        data = {
            "schema_version": self._schema_version,
            "provider_identity": provider_identity or {},
            "entries": [entry.as_dict() for entry in self._entries.values()],
        }
        if self.path is None:
            raise RecordingMissError("RecordingStore has no path configured for saving")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")

    def record(self, entry: RecordingEntry) -> None:
        self._entries[entry.key] = entry

    def lookup(self, key: str) -> RecordingEntry:
        entry = self._entries.get(key)
        if entry is None:
            raise RecordingMissError(f"No recording entry for request key: {key}")
        return entry

    @property
    def schema_version(self) -> int:
        return self._schema_version


def _fingerprint(*parts: Any) -> str:
    serialized = json.dumps(parts, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def model_text_key(*, role: str, prompt: str) -> str:
    return _fingerprint(role, "text", prompt)


def model_json_key(*, role: str, prompt: str, schema: dict[str, Any]) -> str:
    return _fingerprint(role, "json", prompt, schema)


def search_key(query: str, allowed_domains: list[str] | None) -> str:
    return _fingerprint("search", query, sorted(allowed_domains or []))


def embeddings_key(texts: list[str]) -> str:
    return _fingerprint("embeddings", texts)


def plant_data_key(provider: str, scientific_name: str) -> str:
    return _fingerprint("plant_data", provider, scientific_name)


class ReplayTextGenerationProvider(TextGenerationProvider):
    def __init__(self, store: RecordingStore, *, role: str, provider: str, model: str | None) -> None:
        self._store = store
        self._role = role
        self._provider = provider
        self._model = model

    async def generate_text(self, prompt: str, **kwargs: Any) -> TextGenerationResult:
        key = model_text_key(role=self._role, prompt=prompt)
        entry = self._store.lookup(key)
        return TextGenerationResult.model_validate(entry.payload)


class ReplayJsonGenerationProvider(JsonGenerationProvider):
    def __init__(self, store: RecordingStore, *, role: str, provider: str, model: str | None) -> None:
        self._store = store
        self._role = role
        self._provider = provider
        self._model = model

    async def generate_json(
        self, prompt: str, schema: dict[str, Any], **kwargs: Any
    ) -> JsonGenerationResult:
        key = model_json_key(role=self._role, prompt=prompt, schema=schema)
        entry = self._store.lookup(key)
        return JsonGenerationResult.model_validate(entry.payload)


class ReplaySearchProvider(SearchProvider):
    def __init__(self, store: RecordingStore, *, provider: str) -> None:
        self._store = store
        self._provider = provider

    async def search(self, query: str, **kwargs: Any) -> list[SearchResult]:
        allowed_domains = kwargs.get("allowed_domains")
        key = search_key(query, allowed_domains)
        entry = self._store.lookup(key)
        return [SearchResult.model_validate(item) for item in entry.payload.get("results", [])]


class ReplayJudgeEvaluationProvider(JudgeEvaluationProvider):
    def __init__(self, store: RecordingStore, *, provider: str, model: str | None) -> None:
        self._store = store
        self._provider = provider
        self._model = model

    async def judge_response(
        self, payload: dict[str, Any], rubric: dict[str, Any], **kwargs: Any
    ) -> JudgeResult:
        key = model_json_key(role="judge", prompt=json.dumps(payload, sort_keys=True, default=str), schema=rubric)
        entry = self._store.lookup(key)
        return JudgeResult.model_validate(entry.payload)


class ReplayEmbeddingProvider(EmbeddingProvider):
    def __init__(self, store: RecordingStore, *, provider: str, model: str | None) -> None:
        self._store = store
        self._provider = provider
        self._model = model

    async def create_embeddings(self, texts: list[str], **kwargs: Any) -> EmbeddingResult:
        key = embeddings_key(texts)
        entry = self._store.lookup(key)
        return EmbeddingResult.model_validate(entry.payload)


class ReplayPlantDataProvider(PlantDataProvider):
    def __init__(self, store: RecordingStore, *, provider: str) -> None:
        self._store = store
        self._provider = provider

    async def lookup(self, scientific_name: str, **kwargs: Any) -> PlantDataResult | None:
        key = plant_data_key(self._provider, scientific_name)
        entry = self._store.lookup(key)
        payload = entry.payload
        if payload.get("result") is None:
            return None
        return PlantDataResult.model_validate(payload["result"])


class RecordTextGenerationProvider(TextGenerationProvider):
    def __init__(self, inner: TextGenerationProvider, store: RecordingStore, *, role: str, provider: str, model: str | None) -> None:
        self._inner = inner
        self._store = store
        self._role = role
        self._provider = provider
        self._model = model

    async def generate_text(self, prompt: str, **kwargs: Any) -> TextGenerationResult:
        import time

        started = time.perf_counter()
        result = await self._inner.generate_text(prompt, **kwargs)
        latency_ms = (time.perf_counter() - started) * 1000
        self._store.record(
            RecordingEntry(
                key=model_text_key(role=self._role, prompt=prompt),
                role=self._role,
                provider=self._provider,
                model=self._model,
                latency_ms=latency_ms,
                payload=result.model_dump(mode="json"),
            )
        )
        return result


class RecordJsonGenerationProvider(JsonGenerationProvider):
    def __init__(self, inner: JsonGenerationProvider, store: RecordingStore, *, role: str, provider: str, model: str | None) -> None:
        self._inner = inner
        self._store = store
        self._role = role
        self._provider = provider
        self._model = model

    async def generate_json(
        self, prompt: str, schema: dict[str, Any], **kwargs: Any
    ) -> JsonGenerationResult:
        import time

        started = time.perf_counter()
        result = await self._inner.generate_json(prompt, schema, **kwargs)
        latency_ms = (time.perf_counter() - started) * 1000
        self._store.record(
            RecordingEntry(
                key=model_json_key(role=self._role, prompt=prompt, schema=schema),
                role=self._role,
                provider=self._provider,
                model=self._model,
                latency_ms=latency_ms,
                payload=result.model_dump(mode="json"),
            )
        )
        return result


class RecordSearchProvider(SearchProvider):
    def __init__(self, inner: SearchProvider, store: RecordingStore, *, provider: str) -> None:
        self._inner = inner
        self._store = store
        self._provider = provider

    async def search(self, query: str, **kwargs: Any) -> list[SearchResult]:
        import time

        started = time.perf_counter()
        results = await self._inner.search(query, **kwargs)
        latency_ms = (time.perf_counter() - started) * 1000
        allowed_domains = kwargs.get("allowed_domains")
        self._store.record(
            RecordingEntry(
                key=search_key(query, allowed_domains),
                role="search",
                provider=self._provider,
                model=None,
                latency_ms=latency_ms,
                payload={"results": [item.model_dump(mode="json") for item in results]},
            )
        )
        return results


class RecordJudgeEvaluationProvider(JudgeEvaluationProvider):
    def __init__(self, inner: JudgeEvaluationProvider, store: RecordingStore, *, provider: str, model: str | None) -> None:
        self._inner = inner
        self._store = store
        self._provider = provider
        self._model = model

    async def judge_response(
        self, payload: dict[str, Any], rubric: dict[str, Any], **kwargs: Any
    ) -> JudgeResult:
        import time

        started = time.perf_counter()
        result = await self._inner.judge_response(payload, rubric, **kwargs)
        latency_ms = (time.perf_counter() - started) * 1000
        key = model_json_key(role="judge", prompt=json.dumps(payload, sort_keys=True, default=str), schema=rubric)
        self._store.record(
            RecordingEntry(
                key=key,
                role="judge",
                provider=self._provider,
                model=self._model,
                latency_ms=latency_ms,
                payload=result.model_dump(mode="json"),
            )
        )
        return result


class RecordEmbeddingProvider(EmbeddingProvider):
    def __init__(self, inner: EmbeddingProvider, store: RecordingStore, *, provider: str, model: str | None) -> None:
        self._inner = inner
        self._store = store
        self._provider = provider
        self._model = model

    async def create_embeddings(self, texts: list[str], **kwargs: Any) -> EmbeddingResult:
        import time

        started = time.perf_counter()
        result = await self._inner.create_embeddings(texts, **kwargs)
        latency_ms = (time.perf_counter() - started) * 1000
        self._store.record(
            RecordingEntry(
                key=embeddings_key(texts),
                role="embeddings",
                provider=self._provider,
                model=self._model,
                latency_ms=latency_ms,
                payload=result.model_dump(mode="json"),
            )
        )
        return result


class RecordPlantDataProvider(PlantDataProvider):
    def __init__(self, inner: PlantDataProvider, store: RecordingStore, *, provider: str) -> None:
        self._inner = inner
        self._store = store
        self._provider = provider

    async def lookup(self, scientific_name: str, **kwargs: Any) -> PlantDataResult | None:
        import time

        started = time.perf_counter()
        result = await self._inner.lookup(scientific_name, **kwargs)
        latency_ms = (time.perf_counter() - started) * 1000
        self._store.record(
            RecordingEntry(
                key=plant_data_key(self._provider, scientific_name),
                role="plant_data",
                provider=self._provider,
                model=None,
                latency_ms=latency_ms,
                payload={"result": result.model_dump(mode="json") if result else None},
            )
        )
        return result


class ReplayModelProvider(TextGenerationProvider, JsonGenerationProvider):
    """Replay adapter covering both text and JSON generation for the model
    role, so graph calls to both ``generate_text`` and ``generate_json`` work."""

    def __init__(self, store: RecordingStore, *, role: str, provider: str, model: str | None) -> None:
        self._text = ReplayTextGenerationProvider(store, role=role, provider=provider, model=model)
        self._json = ReplayJsonGenerationProvider(store, role=role, provider=provider, model=model)

    async def generate_text(self, prompt: str, **kwargs: Any) -> TextGenerationResult:
        return await self._text.generate_text(prompt, **kwargs)

    async def generate_json(
        self, prompt: str, schema: dict[str, Any], **kwargs: Any
    ) -> JsonGenerationResult:
        return await self._json.generate_json(prompt, schema, **kwargs)


class RecordModelProvider(TextGenerationProvider, JsonGenerationProvider):
    """Record adapter covering both text and JSON generation for the model
    role, forwarding to the real provider and storing responses."""

    def __init__(self, inner: Any, store: RecordingStore, *, role: str, provider: str, model: str | None) -> None:
        self._inner = inner
        self._text = RecordTextGenerationProvider(inner, store, role=role, provider=provider, model=model)
        self._json = RecordJsonGenerationProvider(inner, store, role=role, provider=provider, model=model)

    async def generate_text(self, prompt: str, **kwargs: Any) -> TextGenerationResult:
        return await self._text.generate_text(prompt, **kwargs)

    async def generate_json(
        self, prompt: str, schema: dict[str, Any], **kwargs: Any
    ) -> JsonGenerationResult:
        return await self._json.generate_json(prompt, schema, **kwargs)


__all__ = [
    "RECORDING_SCHEMA_VERSION",
    "RecordEmbeddingProvider",
    "RecordJsonGenerationProvider",
    "RecordJudgeEvaluationProvider",
    "RecordModelProvider",
    "RecordPlantDataProvider",
    "RecordSearchProvider",
    "RecordTextGenerationProvider",
    "RecordingEntry",
    "RecordingError",
    "RecordingMismatchError",
    "RecordingMissError",
    "RecordingMode",
    "RecordingStore",
    "ReplayEmbeddingProvider",
    "ReplayJsonGenerationProvider",
    "ReplayJudgeEvaluationProvider",
    "ReplayModelProvider",
    "ReplayPlantDataProvider",
    "ReplaySearchProvider",
    "ReplayTextGenerationProvider",
    "embeddings_key",
    "model_json_key",
    "model_text_key",
    "plant_data_key",
    "search_key",
]
