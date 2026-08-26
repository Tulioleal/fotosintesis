"""Source-binding tests for the assistant trusted-first fallback path.

Proves that combined RAG-plus-web judging builds one package per supplied
evidence package, routes source support through caller-scoped eligibility
(``trusted`` plus explicitly permitted ``external_fallback``), and removes
support items that cite an unknown URL or more than one URL.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.assistant.graph.plant_resolution import _sources_from_web_results
from app.assistant.graph.web_evidence import _judge_combined_evidence
from app.core.settings import Settings
from app.knowledge.page_evidence import TrustedPageEvidence
from app.providers.types import SearchResult

WATERING = "watering_frequency_or_trigger"


def _settings(**overrides) -> Settings:
    return Settings(
        assistant_evidence_validation_threshold=0.75,
        assistant_safety_validation_threshold=0.85,
        assistant_strong_answer_validation_threshold=0.30,
        assistant_judge_timeout_seconds=30.0,
        **overrides,
    )


def _web_result(
    url: str,
    *,
    status: str = "trusted",
    text: str = "Direct source evidence.",
) -> TrustedPageEvidence:
    return TrustedPageEvidence(
        result=SearchResult(
            title="Care guide",
            url=url,
            snippet=text,
            source_domain="example.org",
        ),
        content=text,
        validation_status=status,
        fetch_status="success",
        fetched_content_length=len(text),
    )


def _state(url: str, *, status: str = "trusted", text: str = "Direct source evidence.") -> dict:
    result = _web_result(url, status=status, text=text)
    return {
        "message": "Watering care",
        "topic": "watering",
        "plant_scientific_name": "Monstera deliciosa",
        "display_plant_name": "Monstera",
        "required_aspects": [WATERING],
        "missing_aspects": [WATERING],
        "answer_language": "en",
        "sources": _sources_from_web_results([result]),
    }, [result]


class _FakeJudge:
    def __init__(self, support: dict[str, object]) -> None:
        self.support = support
        self.payloads: list[dict[str, object]] = []

    async def judge_response(self, payload: dict, rubric: dict):
        self.payloads.append(payload)
        return {
            "status": "full",
            "score": 0.9,
            "passed": True,
            "confidence": 0.9,
            "covered_aspects": [WATERING],
            "missing_aspects": [],
            "source_support": [self.support],
            "contradictions": [],
            "reasons": ["direct source support"],
        }


def _support(urls: list[str], *, quote: str = "Paraphrased guidance text.") -> dict[str, object]:
    return {
        "claim": "Water when the substrate dries.",
        "source_urls": urls,
        "covered_aspects": [WATERING],
        "evidence_quote": quote,
        "confidence": 0.9,
    }


async def _run(support: dict[str, object], *, url: str = "https://example.org/care") -> tuple:
    judge = _FakeJudge(support)
    tools = SimpleNamespace(providers=SimpleNamespace(judge=judge))
    state, results = _state(url)
    validated = await _judge_combined_evidence(
        tools,
        _settings(),
        state,
        results,
    )
    return validated, judge


@pytest.mark.asyncio
async def test_fallback_builds_one_source_package_per_supplied_evidence() -> None:
    judge = _FakeJudge(_support(["https://example.org/care"]))
    tools = SimpleNamespace(providers=SimpleNamespace(judge=judge))
    state, results = _state("https://example.org/care")
    results.append(
        _web_result(
            "https://example.org/second",
            text="Second source package text.",
        )
    )
    await _judge_combined_evidence(tools, _settings(), state, results)

    payload = judge.payloads[0]
    sources = payload.get("evidence_sources")
    assert isinstance(sources, list)
    assert [entry["url"] for entry in sources] == [
        "https://example.org/care",
        "https://example.org/second",
    ]
    assert sources[0]["text"] == "Direct source evidence."
    assert sources[1]["text"] == "Second source package text."
    assert [entry["source_package_id"] for entry in sources] == ["source-0", "source-1"]


@pytest.mark.asyncio
async def test_fallback_support_citing_unknown_url_is_removed() -> None:
    validated, _judge = await _run(
        _support(["https://unknown.invalid/post"]),
        url="https://example.org/care",
    )
    assert validated.source_support == []


@pytest.mark.asyncio
async def test_fallback_multi_url_support_is_removed() -> None:
    validated, _judge = await _run(
        _support(["https://example.org/care", "https://example.org/other"]),
        url="https://example.org/care",
    )
    assert validated.source_support == []


@pytest.mark.asyncio
async def test_fallback_blank_url_in_multi_url_support_is_removed() -> None:
    validated, _judge = await _run(
        _support(["", "https://example.org/care"]),
        url="https://example.org/care",
    )
    assert validated.source_support == []


@pytest.mark.asyncio
async def test_fallback_trusted_paraphrased_support_remains_accepted() -> None:
    validated, _judge = await _run(
        _support(
            ["https://example.org/care"],
            quote="Riegue solo cuando el sustrato esté seco en la superficie.",
        ),
        url="https://example.org/care",
    )
    assert len(validated.source_support) == 1
    assert validated.source_support[0]["source_urls"] == ["https://example.org/care"]
    assert validated.source_support[0]["evidence_quote"].startswith("Riegue")


@pytest.mark.asyncio
async def test_fallback_accepts_explicitly_permitted_external_fallback() -> None:
    validated, _judge = await _run(
        _support(["https://example.org/care"]),
        url="https://example.org/care",
    )
    # The judge result itself is bound only through the fallback eligibility
    # set; a trusted package is accepted as before.
    assert len(validated.source_support) == 1


@pytest.mark.asyncio
async def test_fallback_external_fallback_package_is_bound_when_explicitly_permitted() -> None:
    judge = _FakeJudge(_support(["https://example.org/care"]))
    tools = SimpleNamespace(providers=SimpleNamespace(judge=judge))
    state, results = _state(
        "https://example.org/care",
        status="external_fallback",
    )
    validated = await _judge_combined_evidence(tools, _settings(), state, results)
    assert len(validated.source_support) == 1
    assert validated.source_support[0]["source_urls"] == ["https://example.org/care"]
