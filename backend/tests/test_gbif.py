import json

from app.core.settings import get_settings
from app.identification.gbif import GbifClient

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
