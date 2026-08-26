from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.assistant.care_contracts import RequiredAspect
from app.assistant.graph_shared import AnswerabilityResult
from app.assistant.semantic_coverage import (
    CoverageThresholds,
    SemanticCoverageService,
    SemanticEvidence,
    SemanticSourceEvidence,
)

THRESHOLDS = CoverageThresholds(default=0.75, safety=0.85, strong_full=0.30)
WATERING = RequiredAspect.watering_frequency_or_trigger
LIGHT = RequiredAspect.light_exposure
PET_SAFETY = RequiredAspect.toxicity_pet_safety


def _packaged(
    text: str,
    metadata: tuple[dict[str, object], ...],
    *,
    eligible: frozenset[str] = frozenset({"trusted"}),
) -> SemanticEvidence:
    return SemanticEvidence(
        sources=tuple(
            SemanticSourceEvidence(text=text, metadata=dict(item)) for item in metadata
        ),
        eligible_validation_statuses=frozenset(eligible),
    )


def _support(aspect: RequiredAspect, quote: str = "Direct source evidence.") -> dict[str, object]:
    return {
        "claim": f"Source supports {aspect.value}.",
        "source_urls": [f"https://example.org/{aspect.value}"],
        "covered_aspects": [aspect.value],
        "evidence_quote": quote,
        "confidence": 0.95,
    }


def _evidence(
    aspects: list[RequiredAspect],
    text: str = "Direct source evidence.",
    *,
    validation_status: str | None = "trusted",
) -> SemanticEvidence:
    metadata: list[dict[str, object]] = []
    for aspect in aspects:
        item: dict[str, object] = {"url": f"https://example.org/{aspect.value}"}
        if validation_status is not None:
            item["validation_status"] = validation_status
        metadata.append(item)
    return  _packaged(text, tuple(metadata))


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
        assert request.local_evidence.combined_text == evidence
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
             _packaged(
                "Direct source evidence.",
                (
                    {
                        "url": "https://example.org/watering_frequency_or_trigger",
                        "validation_status": "trusted",
                    },
                ),
            ),
            _support(WATERING, "Not in the supplied evidence."),
            frozenset({WATERING}),
        ),
        (
             _packaged(
                "Direct source evidence.",
                (
                    {
                        "url": "https://different.example/source",
                        "validation_status": "trusted",
                    },
                ),
            ),
            _support(WATERING),
            frozenset(),
        ),
        (
             _packaged(
                "Direct   source\n evidence.",
                (
                    {
                        "url": "https://example.org/watering_frequency_or_trigger",
                        "validation_status": "trusted",
                    },
                ),
            ),
            _support(WATERING, "Direct source evidence."),
            frozenset({WATERING}),
        ),
        (
             _packaged(
                "Direct source evidence.",
                (
                    {
                        "url": "https://example.org/watering_frequency_or_trigger",
                        "validation_status": "untrusted",
                    },
                ),
            ),
            _support(WATERING, "Direct source evidence."),
            frozenset(),
        ),
    ],
    ids=[
        "paraphrased-quote",
        "unknown-source",
        "normalized-whitespace",
        "untrusted-source",
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


@pytest.mark.parametrize(
    ("evidence_text", "quote"),
    [
        (
            "Riegue cuando el sustrato se haya secado por completo en la superficie.",
            "Esperar a que el sustrato esté seco antes de regar.",
        ),
        (
            "Keep the soil evenly moist and never let the plant sit in standing water.",
            "Water only when the top layer of soil feels dry to the touch.",
        ),
        (
            "Brûlez les feuilles en plein soleil direct; préférez une lumière vive filtrée.",
            "La luz solar directa puede dañar las hojas.",
        ),
    ],
    ids=["spanish-paraphrase", "english-synonym-phrasing", "cross-language-summary"],
)
async def test_enrichment_binds_paraphrased_and_multilingual_judge_support(
    evidence_text: str, quote: str
) -> None:
    """Final judge support stays source-bound even when the quote is not an exact
    substring of the supplied evidence text (no lexical coverage gate)."""
    service = SemanticCoverageService()
    evidence =  _packaged(
        evidence_text,
        (
            {
                "url": "https://example.org/watering_frequency_or_trigger",
                "validation_status": "trusted",
            },
        ),
    )

    async def retrieve(required):
        return evidence

    async def judge(request):
        return AnswerabilityResult(
            status="full",
            answerable=True,
            covered_aspects=[WATERING.value],
            source_support=[_support(WATERING, quote)],
            confidence=0.95,
        )

    local = await service.evaluate_local(
        required_aspects=[WATERING],
        retrieve=retrieve,
        judge=judge,
        thresholds=THRESHOLDS,
    )

    assert local.local_covered_aspects == frozenset({WATERING})
    assert local.answerability.source_support[0]["evidence_quote"] == quote


@pytest.mark.parametrize(
    ("support", "expected"),
    [
        (
            {"claim": "", "source_urls": ["https://example.org/watering_frequency_or_trigger"], "covered_aspects": [WATERING.value], "evidence_quote": "quote", "confidence": 0.95},
            frozenset(),
        ),
        (
            {"claim": "Claim.", "source_urls": ["https://example.org/watering_frequency_or_trigger"], "covered_aspects": [WATERING.value], "evidence_quote": "   ", "confidence": 0.95},
            frozenset(),
        ),
        (
            {"claim": "Claim.", "source_urls": "not-a-list", "covered_aspects": [WATERING.value], "evidence_quote": "quote", "confidence": 0.95},
            frozenset(),
        ),
        (
            {"claim": "Claim.", "source_urls": ["https://example.org/watering_frequency_or_trigger"], "covered_aspects": "not-a-list", "evidence_quote": "quote", "confidence": 0.95},
            frozenset(),
        ),
        (
            {"claim": "Claim.", "source_urls": ["https://example.org/watering_frequency_or_trigger"], "covered_aspects": ["unknown_aspect"], "evidence_quote": "quote", "confidence": 0.95},
            frozenset(),
        ),
        (
            {"claim": "Claim.", "source_urls": ["https://example.org/watering_frequency_or_trigger"], "covered_aspects": [WATERING.value], "evidence_quote": "quote", "confidence": 0.95},
            frozenset({WATERING}),
        ),
    ],
    ids=["empty-claim", "blank-quote", "malformed-urls", "malformed-aspects", "non-canonical-aspect", "valid"],
)
async def test_enrichment_binding_rejects_malformed_or_off_registry_support(
    support: dict[str, object], expected: frozenset[RequiredAspect]
) -> None:
    service = SemanticCoverageService()
    evidence =  _packaged(
        "Direct source evidence.",
        (
            {
                "url": "https://example.org/watering_frequency_or_trigger",
                "validation_status": "trusted",
            },
        ),
    )

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


async def test_enrichment_binding_excludes_unrequested_aspects_from_persistence_eligibility() -> None:
    service = SemanticCoverageService()
    evidence =  _packaged(
        "Direct source evidence.",
        (
            {
                "url": "https://example.org/watering_frequency_or_trigger",
                "validation_status": "trusted",
            },
            {
                "url": "https://example.org/light_exposure",
                "validation_status": "trusted",
            },
        ),
    )
    support = [
        {
            "claim": "Source supports watering.",
            "source_urls": ["https://example.org/watering_frequency_or_trigger"],
            "covered_aspects": [WATERING.value, LIGHT.value],
            "evidence_quote": "Direct source evidence.",
            "confidence": 0.95,
        }
    ]

    async def retrieve(required):
        return evidence

    async def judge(request):
        return AnswerabilityResult(
            status="full",
            answerable=True,
            covered_aspects=[WATERING.value],
            source_support=support,
            confidence=0.95,
        )

    local = await service.evaluate_local(
        required_aspects=[WATERING],
        retrieve=retrieve,
        judge=judge,
        thresholds=THRESHOLDS,
    )

    assert local.local_covered_aspects == frozenset({WATERING})
    bound = local.answerability.source_support
    assert len(bound) == 1
    assert bound[0]["covered_aspects"] == [WATERING.value]
    assert LIGHT.value not in bound[0]["covered_aspects"]


async def test_enrichment_binding_requires_safety_confidence_even_when_quote_matches() -> None:
    service = SemanticCoverageService()
    support = _support(PET_SAFETY)
    support["confidence"] = 0.84
    evidence =  _packaged(
        "Direct source evidence.",
        (
            {
                "url": "https://example.org/toxicity_pet_safety",
                "validation_status": "trusted",
            },
        ),
    )

    async def retrieve(required):
        return evidence

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


def _run_binding_evaluation(service, evidence: SemanticEvidence, support=None):
    """Evaluate a single support item against the evidence and return covered aspects."""
    async def _run():
        async def retrieve(required):
            return evidence

        async def judge(request):
            return AnswerabilityResult(
                status="full",
                answerable=True,
                covered_aspects=[WATERING.value],
                source_support=[support or _support(WATERING)],
                confidence=0.95,
            )

        local = await service.evaluate_local(
            required_aspects=[WATERING],
            retrieve=retrieve,
            judge=judge,
            thresholds=THRESHOLDS,
        )
        return local.local_covered_aspects

    import asyncio
    return asyncio.run(_run())


def test_source_binding_rejects_missing_validation_status() -> None:
    service = SemanticCoverageService()
    evidence =  _packaged(
        "Direct source evidence.",
        ({"url": "https://example.org/watering_frequency_or_trigger"},),
    )

    assert _run_binding_evaluation(service, evidence) == frozenset()


def test_source_binding_rejects_blank_validation_status() -> None:
    service = SemanticCoverageService()
    evidence =  _packaged(
        "Direct source evidence.",
        (
            {
                "url": "https://example.org/watering_frequency_or_trigger",
                "validation_status": "   ",
            },
        ),
    )

    assert _run_binding_evaluation(service, evidence) == frozenset()


def test_source_binding_rejects_unknown_validation_status() -> None:
    service = SemanticCoverageService()
    evidence =  _packaged(
        "Direct source evidence.",
        (
            {
                "url": "https://example.org/watering_frequency_or_trigger",
                "validation_status": "review_pending",
            },
        ),
    )

    assert _run_binding_evaluation(service, evidence) == frozenset()


def test_source_binding_rejects_mixed_trusted_and_missing_status() -> None:
    service = SemanticCoverageService()
    evidence = _packaged(
        "Direct source evidence.",
        (
            {
                "url": "https://example.org/watering_frequency_or_trigger",
                "validation_status": "trusted",
            },
            {"url": "https://example.org/watering_frequency_or_trigger"},
        ),
    )

    assert _run_binding_evaluation(service, evidence) == frozenset()


def _run_binding_with_support(service, support: dict[str, object]) -> frozenset[RequiredAspect]:
    return _run_binding_evaluation(service, _evidence([WATERING]), support=support)


def test_source_binding_rejects_multi_url_support() -> None:
    service = SemanticCoverageService()
    support = _support(WATERING)
    support["source_urls"] = [
        "https://example.org/watering_frequency_or_trigger",
        "https://example.org/light_exposure",
    ]

    assert _run_binding_with_support(service, support) == frozenset()


def test_source_binding_rejects_blank_url_in_multi_url_support() -> None:
    service = SemanticCoverageService()
    support = _support(WATERING)
    support["source_urls"] = ["", "https://example.org/watering_frequency_or_trigger"]

    assert _run_binding_with_support(service, support) == frozenset()


def test_source_binding_rejects_duplicate_package_with_unknown_status() -> None:
    service = SemanticCoverageService()
    evidence = _packaged(
        "Direct source evidence.",
        (
            {
                "url": "https://example.org/watering_frequency_or_trigger",
                "validation_status": "trusted",
            },
            {
                "url": "https://example.org/watering_frequency_or_trigger",
                "validation_status": "review_pending",
            },
        ),
    )

    assert _run_binding_evaluation(service, evidence) == frozenset()


def test_source_binding_single_support_cannot_cite_two_sources() -> None:
    service = SemanticCoverageService()
    evidence = _packaged(
        "Direct source evidence.",
        (
            {
                "url": "https://example.org/watering_frequency_or_trigger",
                "validation_status": "trusted",
            },
            {
                "url": "https://example.org/light_exposure",
                "validation_status": "trusted",
            },
        ),
    )
    support = _support(WATERING)
    support["source_urls"] = [
        "https://example.org/watering_frequency_or_trigger",
        "https://example.org/light_exposure",
    ]

    assert _run_binding_evaluation(service, evidence, support=support) == frozenset()


def test_source_binding_accepts_external_fallback_in_permitted_assistant_flow() -> None:
    service = SemanticCoverageService()
    evidence = _packaged(
        "Direct source evidence.",
        (
            {
                "url": "https://example.org/watering_frequency_or_trigger",
                "validation_status": "external_fallback",
            },
        ),
        eligible=frozenset({"trusted", "external_fallback"}),
    )

    assert _run_binding_evaluation(service, evidence) == frozenset({WATERING})


def test_default_semantic_evidence_rejects_external_fallback() -> None:
    service = SemanticCoverageService()
    evidence = _packaged(
        "Direct source evidence.",
        (
            {
                "url": "https://example.org/watering_frequency_or_trigger",
                "validation_status": "external_fallback",
            },
        ),
    )

    assert _run_binding_evaluation(service, evidence) == frozenset()


def test_normal_rag_rejects_external_fallback() -> None:
    """Normal assistant RAG evidence is eligible only for ``trusted``; an
    ``external_fallback`` package must be rejected by the binding layer."""
    service = SemanticCoverageService()
    evidence = _packaged(
        "Direct source evidence.",
        (
            {
                "url": "https://example.org/watering_frequency_or_trigger",
                "validation_status": "external_fallback",
            },
        ),
        eligible=frozenset({"trusted"}),
    )

    assert _run_binding_evaluation(service, evidence) == frozenset()


def test_production_enrichment_rejects_external_fallback() -> None:
    """Production enrichment constructs evidence eligible only for ``trusted``,
    so an ``external_fallback`` package must never be accepted downstream."""
    service = SemanticCoverageService()
    evidence = _packaged(
        "Direct source evidence.",
        (
            {
                "url": "https://example.org/watering_frequency_or_trigger",
                "validation_status": "external_fallback",
            },
        ),
        eligible=frozenset({"trusted"}),
    )

    assert _run_binding_evaluation(service, evidence) == frozenset()
    assert _run_binding_evaluation(service, evidence) != frozenset({WATERING})


def test_source_binding_accepts_trusted_status() -> None:
    service = SemanticCoverageService()
    evidence =  _packaged(
        "Direct source evidence.",
        (
            {
                "url": "https://example.org/watering_frequency_or_trigger",
                "validation_status": "trusted",
            },
        ),
    )

    assert _run_binding_evaluation(service, evidence) == frozenset({WATERING})
