from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.assistant.care_contracts import RequiredAspect
from app.assistant.graph_shared import AnswerabilityResult
from app.assistant.semantic_coverage import (
    CoverageThresholds,
    SemanticCoverageService,
    SemanticEvidence,
)


THRESHOLDS = CoverageThresholds(default=0.75, safety=0.85, strong_full=0.30)
WATERING = RequiredAspect.watering_frequency_or_trigger
LIGHT = RequiredAspect.light_exposure
PET_SAFETY = RequiredAspect.toxicity_pet_safety


def _support(aspect: RequiredAspect, quote: str = "Direct source evidence.") -> dict[str, object]:
    return {
        "claim": f"Source supports {aspect.value}.",
        "source_urls": [f"https://example.org/{aspect.value}"],
        "covered_aspects": [aspect.value],
        "evidence_quote": quote,
        "confidence": 0.95,
    }


def _evidence(
    aspects: list[RequiredAspect], text: str = "Direct source evidence."
) -> SemanticEvidence:
    return SemanticEvidence(
        text,
        tuple({"url": f"https://example.org/{aspect.value}"} for aspect in aspects),
    )


def _result(
    status: str,
    covered: list[RequiredAspect],
    *,
    confidence: float = 0.95,
    contradictions: list[dict[str, object]] | None = None,
) -> AnswerabilityResult:
    return AnswerabilityResult(
        status=status,  # type: ignore[arg-type]
        answerable=status == "full",
        covered_aspects=[aspect.value for aspect in covered],
        source_support=[_support(aspect) for aspect in covered],
        contradictions=contradictions or [],
        confidence=confidence,
    )


async def test_full_local_coverage_skips_final_judge() -> None:
    service = SemanticCoverageService()

    async def retrieve(required):
        assert required == (WATERING, LIGHT)
        return _evidence([WATERING, LIGHT])

    async def local_judge(request):
        assert request.required_aspects == (WATERING, LIGHT)
        return _result("full", [WATERING, LIGHT])

    local = await service.evaluate_local(
        required_aspects=[WATERING, LIGHT],
        retrieve=retrieve,
        judge=local_judge,
        thresholds=THRESHOLDS,
    )

    async def unexpected_final_judge(request):
        raise AssertionError("final judge must not run for complete local coverage")

    final = await service.evaluate_final(
        local=local,
        acquired_evidence=None,
        judge=unexpected_final_judge,
        thresholds=THRESHOLDS,
    )

    assert local.local_covered_aspects == frozenset({WATERING, LIGHT})
    assert local.acquisition_aspects == frozenset()
    assert final.final_covered_aspects == frozenset({WATERING, LIGHT})
    assert final.final_missing_aspects == frozenset()
    assert final.acquisition_used is False


async def test_partial_local_coverage_derives_exact_acquisition_set() -> None:
    service = SemanticCoverageService()

    async def retrieve(required):
        return _evidence([WATERING])

    async def judge(request):
        return _result("partial", [WATERING])

    local = await service.evaluate_local(
        required_aspects=[WATERING, LIGHT, WATERING],
        retrieve=retrieve,
        judge=judge,
        thresholds=THRESHOLDS,
    )

    assert local.required_aspects == frozenset({WATERING, LIGHT})
    assert local.local_covered_aspects == frozenset({WATERING})
    assert local.acquisition_aspects == frozenset({LIGHT})
    assert local.initial_missing_aspects == frozenset({LIGHT})


async def test_acquired_evidence_can_complete_coverage_and_receives_all_aspects() -> None:
    service = SemanticCoverageService()

    async def retrieve(required):
        return _evidence([WATERING])

    async def local_judge(request):
        return _result("partial", [WATERING])

    local = await service.evaluate_local(
        required_aspects=[WATERING, LIGHT],
        retrieve=retrieve,
        judge=local_judge,
        thresholds=THRESHOLDS,
    )
    acquired = _evidence([LIGHT])

    async def final_judge(request):
        assert request.required_aspects == (WATERING, LIGHT)
        assert request.local_evidence is local.evidence
        assert request.local_answerability is local.answerability
        assert request.acquired_evidence is acquired
        return _result("full", [WATERING, LIGHT])

    final = await service.evaluate_final(
        local=local,
        acquired_evidence=acquired,
        judge=final_judge,
        thresholds=THRESHOLDS,
    )

    assert final.final_covered_aspects == frozenset({WATERING, LIGHT})
    assert final.final_missing_aspects == frozenset()
    assert final.acquisition_used is True


async def test_final_combined_judge_can_revise_local_coverage() -> None:
    service = SemanticCoverageService()

    async def retrieve(required):
        return _evidence([WATERING])

    async def local_judge(request):
        return _result("partial", [WATERING])

    local = await service.evaluate_local(
        required_aspects=[WATERING, LIGHT],
        retrieve=retrieve,
        judge=local_judge,
        thresholds=THRESHOLDS,
    )

    async def final_judge(request):
        return _result("partial", [LIGHT])

    final = await service.evaluate_final(
        local=local,
        acquired_evidence=_evidence([LIGHT]),
        judge=final_judge,
        thresholds=THRESHOLDS,
    )

    assert final.local_covered_aspects == frozenset({WATERING})
    assert final.final_covered_aspects == frozenset({LIGHT})
    assert final.final_missing_aspects == frozenset({WATERING})


@pytest.mark.parametrize("status", ["insufficient", "contradictory"])
async def test_unanswerable_local_results_remain_conservative(status: str) -> None:
    service = SemanticCoverageService()
    contradiction = {
        "claim_a": "Water weekly.",
        "claim_b": "Water monthly.",
        "source_a_urls": ["https://example.org/a"],
        "source_b_urls": ["https://example.org/b"],
    }

    async def retrieve(required):
        return _evidence([])

    async def judge(request):
        return _result(
            status,
            [],
            contradictions=[contradiction] if status == "contradictory" else None,
        )

    local = await service.evaluate_local(
        required_aspects=[WATERING],
        retrieve=retrieve,
        judge=judge,
        thresholds=THRESHOLDS,
    )

    assert local.local_covered_aspects == frozenset()
    assert local.initial_missing_aspects == frozenset({WATERING})
    assert local.answerability.status == status


def test_safety_coverage_requires_registry_threshold_and_direct_support() -> None:
    service = SemanticCoverageService()
    low_confidence = _result("full", [PET_SAFETY], confidence=0.84)
    missing_direct_support = AnswerabilityResult(
        status="partial",
        covered_aspects=[PET_SAFETY.value, WATERING.value],
        source_support=[_support(WATERING)],
        confidence=0.95,
    )

    low = service.normalized_coverage(
        low_confidence,
        required_aspects=[PET_SAFETY],
        thresholds=THRESHOLDS,
    )
    indirect = service.normalized_coverage(
        missing_direct_support,
        required_aspects=[PET_SAFETY, WATERING],
        thresholds=THRESHOLDS,
    )

    assert low.status == "insufficient"
    assert low.missing_aspects == [PET_SAFETY.value]
    assert indirect.covered_aspects == [WATERING.value]
    assert indirect.missing_aspects == [PET_SAFETY.value]


def test_malformed_judge_output_degrades_to_typed_insufficient() -> None:
    service = SemanticCoverageService()
    malformed = SimpleNamespace(
        status="unexpected",
        passed=True,
        covered_aspects={"not": "a list"},
        source_support="not support objects",
        confidence="not a number",
    )

    result = service.normalized_coverage(
        malformed,
        required_aspects=[WATERING],
        thresholds=THRESHOLDS,
    )

    assert result.status == "insufficient"
    assert result.answerable is False
    assert result.covered_aspects == []
    assert result.missing_aspects == [WATERING.value]
    assert result.confidence == 0.0


@pytest.mark.parametrize(
    ("evidence", "quote"),
    [
        ("Riegue cuando el sustrato se haya secado.", "cuando el sustrato se haya secado"),
        ("Irrigate after the growing medium loses surface moisture.", "loses surface moisture"),
        (
            "Wait until the upper layer no longer feels damp before adding water.",
            "no longer feels damp",
        ),
    ],
    ids=["non-english", "synonym", "paraphrase"],
)
async def test_semantic_wording_reaches_judge_without_deterministic_gate(
    evidence: str, quote: str
) -> None:
    service = SemanticCoverageService()

    async def retrieve(required):
        return _evidence([WATERING], evidence)

    async def judge(request):
        assert request.local_evidence.text == evidence
        result = _result("full", [WATERING])
        return AnswerabilityResult(
            status=result.status,
            answerable=result.answerable,
            covered_aspects=result.covered_aspects,
            source_support=[_support(WATERING, quote)],
            confidence=result.confidence,
        )

    local = await service.evaluate_local(
        required_aspects=[WATERING],
        retrieve=retrieve,
        judge=judge,
        thresholds=THRESHOLDS,
    )

    assert local.local_covered_aspects == frozenset({WATERING})
    assert local.acquisition_aspects == frozenset()


@pytest.mark.parametrize(
    ("evidence", "support", "expected"),
    [
        (
            SemanticEvidence(
                "Direct source evidence.",
                ({"url": "https://example.org/watering_frequency_or_trigger"},),
            ),
            _support(WATERING, "Not in the supplied evidence."),
            frozenset(),
        ),
        (
            SemanticEvidence(
                "Direct source evidence.",
                ({"url": "https://different.example/source"},),
            ),
            _support(WATERING),
            frozenset(),
        ),
        (
            SemanticEvidence(
                "Direct   source\n evidence.",
                ({"url": "https://example.org/watering_frequency_or_trigger"},),
            ),
            _support(WATERING, "Direct source evidence."),
            frozenset({WATERING}),
        ),
    ],
)
async def test_enrichment_coverage_binds_support_to_supplied_evidence(
    evidence: SemanticEvidence,
    support: dict[str, object],
    expected: frozenset[RequiredAspect],
) -> None:
    service = SemanticCoverageService()

    async def retrieve(required):
        return evidence

    async def judge(request):
        return AnswerabilityResult(
            status="full",
            answerable=True,
            covered_aspects=[WATERING.value],
            source_support=[support],
            confidence=0.95,
        )

    local = await service.evaluate_local(
        required_aspects=[WATERING],
        retrieve=retrieve,
        judge=judge,
        thresholds=THRESHOLDS,
    )

    assert local.local_covered_aspects == expected


async def test_enrichment_safety_requires_bound_support_confidence() -> None:
    service = SemanticCoverageService()
    support = _support(PET_SAFETY)
    support["confidence"] = 0.84

    async def retrieve(required):
        return _evidence([PET_SAFETY])

    async def judge(request):
        return AnswerabilityResult(
            status="full",
            answerable=True,
            covered_aspects=[PET_SAFETY.value],
            source_support=[support],
            confidence=0.95,
        )

    local = await service.evaluate_local(
        required_aspects=[PET_SAFETY],
        retrieve=retrieve,
        judge=judge,
        thresholds=THRESHOLDS,
    )

    assert local.local_covered_aspects == frozenset()
