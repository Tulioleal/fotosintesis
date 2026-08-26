import json
from pathlib import Path

import pytest

from app.evaluation.recordings import (
    RECORDING_SCHEMA_VERSION,
    RecordingEntry,
    RecordingMismatchError,
    RecordingMissError,
    RecordingMode,
    RecordingStore,
    ReplayEmbeddingProvider,
    ReplayModelProvider,
    ReplaySearchProvider,
    embeddings_key,
    model_json_key,
    model_text_key,
    search_key,
)
from app.providers.types import (
    EmbeddingResult,
    JsonGenerationResult,
    SearchResult,
    TextGenerationResult,
)


def test_recording_store_roundtrip_save_and_load(tmp_path: Path) -> None:
    path = tmp_path / "recording.json"
    store = RecordingStore(path)
    store.record(
        RecordingEntry(
            key="k1",
            role="model",
            provider="mock",
            model="mock-text",
            latency_ms=1.0,
            payload={"text": "hello"},
        )
    )
    store.save(provider_identity={"model": "mock"})

    loaded = RecordingStore.load(path, expected_provider_identity={"model": "mock"})
    assert loaded.schema_version == RECORDING_SCHEMA_VERSION
    entry = loaded.lookup("k1")
    assert entry.payload == {"text": "hello"}
    assert entry.provider == "mock"


def test_recording_missing_key_raises_miss_error(tmp_path: Path) -> None:
    path = tmp_path / "recording.json"
    store = RecordingStore(path)
    store.record(RecordingEntry(key="k1", role="model", provider="mock", model=None, latency_ms=None, payload={}))
    store.save()

    loaded = RecordingStore.load(path)
    with pytest.raises(RecordingMissError):
        loaded.lookup("missing-key")


def test_recording_missing_file_raises_miss_error(tmp_path: Path) -> None:
    with pytest.raises(RecordingMissError):
        RecordingStore.load(tmp_path / "does-not-exist.json")


def test_recording_schema_version_mismatch_raises(tmp_path: Path) -> None:
    path = tmp_path / "recording.json"
    path.write_text(json.dumps({"schema_version": 999, "provider_identity": {}, "entries": []}), encoding="utf-8")
    with pytest.raises(RecordingMismatchError, match="schema version"):
        RecordingStore.load(path)


def test_recording_provider_identity_mismatch_raises(tmp_path: Path) -> None:
    path = tmp_path / "recording.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": RECORDING_SCHEMA_VERSION,
                "provider_identity": {"model": "old-provider"},
                "entries": [],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(RecordingMismatchError, match="provider identity"):
        RecordingStore.load(path, expected_provider_identity={"model": "new-provider"})


def test_replay_lookups_are_keyed_and_deterministic(tmp_path: Path) -> None:
    path = tmp_path / "recording.json"
    store = RecordingStore(path)
    store.record(
        RecordingEntry(
            key=model_text_key(role="model", prompt="say hi"),
            role="model",
            provider="mock",
            model="mock-text",
            latency_ms=None,
            payload={"text": "replayed-text", "provider": "mock"},
        )
    )
    store.save()

    loaded = RecordingStore.load(path)
    provider = ReplayModelProvider(loaded, role="model", provider="mock", model="mock-text")
    import asyncio

    replayed = asyncio.run(provider.generate_text("say hi"))
    assert replayed.text == "replayed-text"


def test_replay_embedding_and_search_providers(tmp_path: Path) -> None:
    import asyncio

    path = tmp_path / "recording.json"
    store = RecordingStore(path)
    store.record(
        RecordingEntry(
            key=embeddings_key(["a", "b"]),
            role="embeddings",
            provider="mock",
            model="mock-embed",
            latency_ms=None,
            payload={"embeddings": [[1.0], [2.0]], "provider": "mock"},
        )
    )
    store.record(
        RecordingEntry(
            key=search_key("monstera", ["example.org"]),
            role="search",
            provider="mock",
            model=None,
            latency_ms=None,
            payload={"results": [{"title": "t", "url": "https://example.org/x", "snippet": "s", "source_domain": "example.org"}]},
        )
    )
    store.save()
    loaded = RecordingStore.load(path)

    embeds = asyncio.run(ReplayEmbeddingProvider(loaded, provider="mock", model="mock-embed").create_embeddings(["a", "b"]))
    assert embeds.embeddings == [[1.0], [2.0]]

    results = asyncio.run(ReplaySearchProvider(loaded, provider="mock").search("monstera", allowed_domains=["example.org"]))
    assert results[0].url == "https://example.org/x"


def test_recording_mode_enum() -> None:
    assert RecordingMode.record.value == "record"
    assert RecordingMode.replay.value == "replay"
