import json

import pytest

from app.core.settings import get_settings
from app.identification.gbif import GbifClient, ProviderLookupError

PUBLIC_GBIF_URL = "https://api.gbif.org/v1/species/match"


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._body = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *args: object) -> bool:
        return False


def test_public_gbif_url_remains_default(monkeypatch) -> None:
    monkeypatch.delenv("GBIF_BASE_URL", raising=False)
    get_settings.cache_clear()
    assert GbifClient().base_url == PUBLIC_GBIF_URL


async def test_configured_base_url_is_used(
    monkeypatch,
) -> None:
    captured = {}

    def fake_urlopen(url, timeout):
        captured["url"] = url
        captured["timeout"] = timeout
        return _FakeResponse({"matchType": "NONE", "confidence": 0})

    monkeypatch.setattr("app.identification.gbif.urlopen", fake_urlopen)
    client = GbifClient(base_url="http://mock-gbif:8080/v1/species/match")

    assert (await client.match_name("Monstera deliciosa")).matched is False
    assert captured["url"].startswith(
        "http://mock-gbif:8080/v1/species/match?name=Monstera+deliciosa"
    )


async def test_cotyledon_tomentosa_produces_canonical_identity(
    monkeypatch,
) -> None:
    payload = {
        "usageKey": 4219524,
        "acceptedUsageKey": 4219524,
        "scientificName": "Cotyledon tomentosa Harv.",
        "acceptedScientificName": "Cotyledon tomentosa Harv.",
        "canonicalName": "Cotyledon tomentosa",
        "status": "ACCEPTED",
        "matchType": "EXACT",
        "confidence": 100,
        "synonym": False,
        "genus": "Cotyledon",
        "family": "Crassulaceae",
        "species": "Cotyledon tomentosa",
    }
    monkeypatch.setattr(
        "app.identification.gbif.urlopen", lambda url, timeout: _FakeResponse(payload)
    )

    taxonomy = await GbifClient(base_url=PUBLIC_GBIF_URL).match_name(
        "Cotyledon tomentosa"
    )

    assert taxonomy.matched is True
    assert taxonomy.accepted_key == 4219524
    assert taxonomy.binomial_name == "Cotyledon tomentosa"
    assert taxonomy.has_canonical_identity is True


async def test_none_response_remains_unmatched(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.identification.gbif.urlopen",
        lambda url, timeout: _FakeResponse({"matchType": "NONE", "confidence": 0}),
    )

    taxonomy = await GbifClient(base_url=PUBLIC_GBIF_URL).match_name(
        "Monstera deliciosa"
    )

    assert taxonomy.matched is False
    assert taxonomy.has_canonical_identity is False


async def test_match_provider_failure_is_retryable(monkeypatch) -> None:
    attempts = 0
    delays: list[float] = []

    def fake_urlopen(url, timeout):
        nonlocal attempts
        attempts += 1
        raise OSError("network down")

    monkeypatch.setattr("app.identification.gbif.urlopen", fake_urlopen)
    monkeypatch.setattr("app.identification.gbif.sleep", delays.append)

    with pytest.raises(ProviderLookupError) as exc_info:
        await GbifClient(base_url=PUBLIC_GBIF_URL).match_name("Monstera deliciosa")

    assert attempts == 3
    assert delays == [0.2, 0.4]
    assert exc_info.value.cause_type == "OSError"
    assert exc_info.value.attempts == 3
    assert exc_info.value.latency_seconds is not None


async def test_match_recovers_after_transient_provider_failure(monkeypatch) -> None:
    attempts = 0
    delays: list[float] = []
    payload = {
        "usageKey": 2868323,
        "acceptedUsageKey": 2868323,
        "scientificName": "Epipremnum aureum (Linden & André) G.S.Bunting",
        "acceptedScientificName": "Epipremnum aureum (Linden & André) G.S.Bunting",
        "canonicalName": "Epipremnum aureum",
        "status": "ACCEPTED",
        "matchType": "EXACT",
        "confidence": 100,
        "genus": "Epipremnum",
        "family": "Araceae",
        "species": "Epipremnum aureum",
    }

    def fake_urlopen(url, timeout):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise OSError("temporary DNS failure")
        return _FakeResponse(payload)

    monkeypatch.setattr("app.identification.gbif.urlopen", fake_urlopen)
    monkeypatch.setattr("app.identification.gbif.sleep", delays.append)

    taxonomy = await GbifClient(base_url=PUBLIC_GBIF_URL).match_name(
        "Epipremnum aureum"
    )

    assert attempts == 2
    assert delays == [0.2]
    assert taxonomy.has_canonical_identity is True
    assert taxonomy.accepted_key == 2868323


async def test_suggest_prioritizes_accepted_species(monkeypatch) -> None:
    payload = [
        {
            "key": 1001,
            "canonicalName": "Monstera deliciosa",
            "scientificName": "Monstera deliciosa Liebm.",
            "status": "ACCEPTED",
            "rank": "SPECIES",
            "genus": "Monstera",
            "family": "Araceae",
            "species": "Monstera deliciosa",
        },
        {
            "key": 1002,
            "canonicalName": "Monstera deliciosa subsp. sierrana",
            "scientificName": "Monstera deliciosa subsp. sierrana",
            "status": "ACCEPTED",
            "rank": "SUBSPECIES",
            "genus": "Monstera",
            "family": "Araceae",
            "species": "Monstera deliciosa",
        },
    ]

    def fake_urlopen(url, timeout):
        return _FakeResponse(payload)

    monkeypatch.setattr("app.identification.gbif.urlopen", fake_urlopen)

    result = await GbifClient(base_url=PUBLIC_GBIF_URL).suggest("Monstera")

    assert len(result) == 2
    # Accepted species-level candidate is ranked first.
    assert result[0].key == 1001
    assert result[0].rank == "SPECIES"
    assert result[0].accepted_scientific_name == "Monstera deliciosa Liebm."
    assert result[0].binomial_name == "Monstera deliciosa"
    assert result[0].genus == "Monstera"
    assert result[0].family == "Araceae"
    assert result[0].matched is True
    assert result[1].rank == "SUBSPECIES"


async def test_suggest_provider_failure_is_retryable(monkeypatch) -> None:
    def fake_urlopen(url, timeout):
        raise OSError("network down")

    monkeypatch.setattr("app.identification.gbif.urlopen", fake_urlopen)

    with pytest.raises(ProviderLookupError):
        await GbifClient(base_url=PUBLIC_GBIF_URL).suggest("Monstera")


async def test_suggest_ignores_unranked_or_missing_key(monkeypatch) -> None:
    payload = [
        {"canonicalName": "No key here", "status": "ACCEPTED"},
        {"key": 2001, "canonicalName": "Valid entry", "status": "ACCEPTED", "rank": "SPECIES"},
    ]

    def fake_urlopen(url, timeout):
        return _FakeResponse(payload)

    monkeypatch.setattr("app.identification.gbif.urlopen", fake_urlopen)

    result = await GbifClient(base_url=PUBLIC_GBIF_URL).suggest("query")

    assert len(result) == 1
    assert result[0].key == 2001
