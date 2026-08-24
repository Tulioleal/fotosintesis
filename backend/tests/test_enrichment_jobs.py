from datetime import UTC, datetime, timezone
from uuid import uuid4

import pytest

from app.providers.errors import ProviderError
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from app.assistant.care_contracts import RequiredAspect
from app.enrichment.acquisition import OfflineEnrichmentAcquisitionService
from app.enrichment.evidence import (
    AcceptedEnrichmentClaim,
    EnrichmentEvidencePersistenceService,
    enrichment_content_key,
    stable_enrichment_chunk_id,
    stable_enrichment_document_id,
)
from app.enrichment.identity import CanonicalSpeciesIdentity
from app.enrichment.policy import ENRICHMENT_POLICY_V1
from app.enrichment.progress import (
    EnrichmentJobProgress,
    EnrichmentProgressRepository,
    build_efficacy_snapshot,
    build_failure_terminal_result,
)
from app.enrichment.service import EnrichmentExecution, _accepted_acquired_claims
from app.jobs.handler import HandlerRegistry
from app.jobs.handlers.enrich_confirmed_plant import EnrichConfirmedPlantHandler
from app.jobs.schemas import (
    EnrichConfirmedPlantPayload,
    EnrichmentJobResult,
    EnrichmentLimitation,
    JobFailureCategory,
    JobStatus,
    JobType,
)
from app.knowledge.acquisition import TrustedSourceValidator
from app.knowledge.page_evidence import TrustedPageEvidence
from app.knowledge.schemas import (
    EnrichmentEvidenceMetadata,
    EnrichmentEvidenceState,
    KnowledgeChunk,
    PersistedKnowledgeDocument,
    ReviewStatus,
)
from app.providers.types import SearchResult


def _payload() -> EnrichConfirmedPlantPayload:
    run_id = uuid4()
    return EnrichConfirmedPlantPayload.model_validate(
        {
            "payload_version": 1,
            "policy_version": 1,
            "species": {
                "accepted_gbif_key": 2878688,
                "normalized_binomial": "Monstera deliciosa",
            },
            "taxonomy_provenance_id": str(uuid4()),
            "run_id": str(run_id),
        }
    )


class FakeExecutionService:
    def __init__(self, *outcomes) -> None:
        self.outcomes = list(outcomes)
        self.calls = 0

    async def execute(self, payload):
        outcome = self.outcomes[min(self.calls, len(self.outcomes) - 1)]
        self.calls += 1
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


def _execution(*, covered: tuple[RequiredAspect, ...], avoided: bool = False):
    required = tuple(
        aspect
        for aspect in RequiredAspect
        if aspect in ENRICHMENT_POLICY_V1.required_aspects
    )
    return EnrichmentExecution(
        covered_aspects=covered,
        missing_aspects=tuple(aspect for aspect in required if aspect not in covered),
        acquisition_avoided=avoided,
    )


def test_enrichment_payload_is_versioned_and_bounded_result_is_separate_from_error() -> None:
    payload = _payload()
    assert payload.species.accepted_gbif_key == 2878688
    assert payload.species.normalized_binomial == "Monstera deliciosa"
    unsupported = EnrichConfirmedPlantPayload.model_validate(
        {**payload.model_dump(mode="json"), "policy_version": 2}
    )
    assert unsupported.policy_version == 2
    with pytest.raises(ValidationError):
        EnrichmentJobResult(
            outcome="partial",
            policy_version=1,
            covered_aspects=[],
            missing_aspects=[RequiredAspect.light_exposure.value],
            covered_count=0,
            missing_count=1,
            limitations=["missing_required_aspects"],
        )


@pytest.mark.asyncio
async def test_handler_maps_covered_partial_complete_and_insufficient_outcomes() -> None:
    required = tuple(
        aspect
        for aspect in RequiredAspect
        if aspect in ENRICHMENT_POLICY_V1.required_aspects
    )
    complete = await EnrichConfirmedPlantHandler(
        FakeExecutionService(_execution(covered=required, avoided=True))
    ).handle(payload=_payload(), attempt_count=1, max_attempts=3)
    acquired_complete = await EnrichConfirmedPlantHandler(
        FakeExecutionService(_execution(covered=required, avoided=False))
    ).handle(payload=_payload(), attempt_count=1, max_attempts=3)
    partial = await EnrichConfirmedPlantHandler(
        FakeExecutionService(_execution(covered=(RequiredAspect.light_exposure,)))
    ).handle(payload=_payload(), attempt_count=1, max_attempts=3)
    insufficient = await EnrichConfirmedPlantHandler(
        FakeExecutionService(_execution(covered=()))
    ).handle(payload=_payload(), attempt_count=1, max_attempts=3)

    assert complete.status is JobStatus.complete
    assert complete.result and complete.result.acquisition_avoided is True
    assert acquired_complete.status is JobStatus.complete
    assert acquired_complete.result and acquired_complete.result.acquisition_avoided is False
    assert partial.status is JobStatus.partial
    assert partial.result and partial.result.covered_count == 1
    assert insufficient.status is JobStatus.failed
    assert insufficient.result is None
    assert insufficient.error and insufficient.error.category is JobFailureCategory.insufficient_evidence

    assert complete.efficacy is not None
    assert complete.efficacy.acquisition_avoided is True
    assert complete.efficacy.final_covered_count == len(required)
    assert complete.efficacy.coverage_gain == len(required)
    assert partial.efficacy is not None
    assert partial.efficacy.final_covered_count == 1
    assert partial.efficacy.accepted_aspect_count == 0
    assert insufficient.efficacy is not None
    assert insufficient.efficacy.final_covered_count == 0
    assert insufficient.efficacy.coverage_gain == 0


@pytest.mark.asyncio
async def test_handler_attaches_bounded_snapshot_to_execution_failures() -> None:
    for error in (
        TimeoutError(),
        IntegrityError("insert", {}, Exception("constraint")),
        ValueError("invariant"),
    ):
        result = await EnrichConfirmedPlantHandler(FakeExecutionService(error)).handle(
            payload=_payload(), attempt_count=1, max_attempts=3
        )
        assert result.status is JobStatus.failed
        assert result.efficacy is not None
        assert result.efficacy.policy_version == 1
        assert result.efficacy.local_covered_count == 0
        assert result.efficacy.final_covered_count == 0
        assert result.efficacy.coverage_gain == 0
        assert result.efficacy.accepted_aspect_count == 0
        assert result.efficacy.search_count == 0
        assert result.efficacy.acquisition_avoided is False


@pytest.mark.asyncio
async def test_handler_does_not_emit_runtime_metrics() -> None:
    from app.observability.metrics import MetricsRegistry

    metrics = MetricsRegistry()
    handler = EnrichConfirmedPlantHandler(
        FakeExecutionService(
            _execution(covered=(RequiredAspect.light_exposure,))
        )
    )
    await handler.handle(payload=_payload(), attempt_count=1, max_attempts=3)
    assert metrics.enrichment_efficacy_counts == {}
    assert metrics.enrichment_efficacy_histograms == {}


@pytest.mark.asyncio
async def test_handler_maps_safety_rejection_and_operational_retries() -> None:
    covered = tuple(
        aspect
        for aspect in ENRICHMENT_POLICY_V1.required_aspects
        if aspect is not RequiredAspect.toxicity_pet_safety
    )
    safety_rejected = EnrichmentExecution(
        covered_aspects=covered,
        missing_aspects=(RequiredAspect.toxicity_pet_safety,),
        acquisition_avoided=False,
        safety_evidence_rejected=True,
    )
    service = FakeExecutionService(TimeoutError(), safety_rejected)
    handler = EnrichConfirmedPlantHandler(service)

    retry = await handler.handle(payload=_payload(), attempt_count=1, max_attempts=3)
    success = await handler.handle(payload=_payload(), attempt_count=2, max_attempts=3)

    assert retry.status is JobStatus.failed
    assert retry.error and retry.error.retryable is True
    assert retry.error.category is JobFailureCategory.provider_transient
    assert success.status is JobStatus.partial
    assert success.result and "safety_evidence_rejected" in success.result.limitations


@pytest.mark.asyncio
async def test_handler_maps_integrity_error_to_permanent_invariant_failure() -> None:
    error = IntegrityError("insert", {}, Exception("constraint"))
    result = await EnrichConfirmedPlantHandler(FakeExecutionService(error)).handle(
        payload=_payload(), attempt_count=1, max_attempts=3
    )

    assert result.status is JobStatus.failed
    assert result.error and result.error.category is JobFailureCategory.invariant_violation
    assert result.error.retryable is False


@pytest.mark.asyncio
async def test_handler_keeps_retryable_failure_on_attempt_exhaustion_for_worker_mapping() -> None:
    result = await EnrichConfirmedPlantHandler(FakeExecutionService(TimeoutError())).handle(
        payload=_payload(),
        attempt_count=3,
        max_attempts=3,
    )

    assert result.status is JobStatus.failed
    assert result.error and result.error.retryable is True
    assert result.error.category is JobFailureCategory.provider_transient


@pytest.mark.asyncio
async def test_handler_rejects_invalid_attempt_contract_and_registry_versions() -> None:
    handler = EnrichConfirmedPlantHandler(FakeExecutionService(_execution(covered=())))
    result = await handler.handle(payload=_payload(), attempt_count=1, max_attempts=4)
    registry = HandlerRegistry()
    registry.register(
        JobType.enrich_confirmed_plant.value,
        handler,
        payload_models={1: EnrichConfirmedPlantPayload},
    )

    assert result.error and result.error.category is JobFailureCategory.invariant_violation
    assert registry.get_payload_model(JobType.enrich_confirmed_plant.value, 2) is None


class RecordingSearch:
    def __init__(self) -> None:
        self.queries: list[str] = []

    async def search(self, query: str, **kwargs):
        self.queries.append(query)
        return [
            SearchResult(
                title="Trusted",
                url=f"https://example.org/{len(self.queries)}",
                snippet="Direct evidence",
                source_domain="example.org",
            )
        ]


class RecordingFetcher:
    async def fetch_all(self, results, *, limit=3):
        return [TrustedPageEvidence(result=result, content=result.snippet) for result in results[:limit]]


class FetchedRecordingFetcher:
    async def fetch_all(self, results, *, limit=3):
        return [
            TrustedPageEvidence(
                result=result,
                content=result.snippet,
                fetch_status="fetched",
            )
            for result in results[:limit]
        ]


class PartiallyFailingSearch(RecordingSearch):
    async def search(self, query: str, **kwargs):
        if self.queries:
            from app.providers.errors import ProviderError

            self.queries.append(query)
            raise ProviderError("temporary search failure")
        return await super().search(query, **kwargs)


@pytest.mark.asyncio
async def test_offline_acquisition_searches_only_missing_policy_groups_within_bounds() -> None:
    search = RecordingSearch()
    missing = (
        RequiredAspect.light_exposure,
        RequiredAspect.soil_drainage,
        RequiredAspect.toxicity_pet_safety,
    )
    result = await OfflineEnrichmentAcquisitionService(
        search=search,
        trusted_sources=TrustedSourceValidator(["example.org"]),
        page_fetcher=RecordingFetcher(),
    ).acquire(
        identity=CanonicalSpeciesIdentity(2878688, "Monstera deliciosa", True),
        required_aspects=tuple(ENRICHMENT_POLICY_V1.required_aspects),
        acquisition_aspects=missing,
        policy=ENRICHMENT_POLICY_V1,
    )

    assert set(aspect for group in result.searched_groups for aspect in group) == set(missing)
    assert all(len(group) <= 4 for group in result.searched_groups)
    assert len(search.queries) == len(result.searched_groups) <= 5
    assert RequiredAspect.watering_amount not in {
        aspect for group in result.searched_groups for aspect in group
    }


@pytest.mark.asyncio
async def test_offline_acquisition_keeps_evidence_when_later_search_group_fails() -> None:
    search = PartiallyFailingSearch()
    missing = (
        RequiredAspect.general_care_summary,
        RequiredAspect.light_exposure,
    )

    result = await OfflineEnrichmentAcquisitionService(
        search=search,
        trusted_sources=TrustedSourceValidator(["example.org"]),
        page_fetcher=FetchedRecordingFetcher(),
    ).acquire(
        identity=CanonicalSpeciesIdentity(2878688, "Monstera deliciosa", True),
        required_aspects=tuple(ENRICHMENT_POLICY_V1.required_aspects),
        acquisition_aspects=missing,
        policy=ENRICHMENT_POLICY_V1,
    )

    assert len(search.queries) == 2
    assert len(result.evidence) == 1
    assert result.evidence[0].result.url == "https://example.org/1"


@pytest.mark.asyncio
async def test_offline_acquisition_raises_retryable_when_partial_outage_yields_no_evidence() -> None:
    search = PartiallyFailingSearch()
    missing = (
        RequiredAspect.general_care_summary,
        RequiredAspect.light_exposure,
    )

    class EmptyFetcher:
        async def fetch_all(self, results, *, limit=3):
            return []

    with pytest.raises(ProviderError, match="temporary search failure"):
        await OfflineEnrichmentAcquisitionService(
            search=search,
            trusted_sources=TrustedSourceValidator(["example.org"]),
            page_fetcher=EmptyFetcher(),
        ).acquire(
            identity=CanonicalSpeciesIdentity(2878688, "Monstera deliciosa", True),
            required_aspects=tuple(ENRICHMENT_POLICY_V1.required_aspects),
            acquisition_aspects=missing,
            policy=ENRICHMENT_POLICY_V1,
        )


def test_only_final_supported_trusted_acquired_claims_are_selected() -> None:
    trusted_page = TrustedPageEvidence(
        result=SearchResult(
            title="Trusted",
            url="https://example.org/light",
            snippet="Bright indirect light is suitable.",
            source_domain="example.org",
        ),
        content="Bright indirect light is suitable.",
        fetch_status="fetched",
    )
    untrusted_page = TrustedPageEvidence(
        result=SearchResult(
            title="Rejected",
            url="https://example.org/rejected",
            snippet="Snippet text.",
            source_domain="example.org",
        ),
        content="Snippet text.",
        fetch_status="fetched",
        validation_status="rejected",
    )
    blank_status_page = TrustedPageEvidence(
        result=SearchResult(
            title="Blank",
            url="https://example.org/blank",
            snippet="Snippet text.",
            source_domain="example.org",
        ),
        content="Snippet text.",
        fetch_status="fetched",
        validation_status="",
    )
    support = [
        {
            "claim": "Use bright indirect light.",
            "evidence_quote": "Bright indirect light is suitable.",
            "source_urls": ["https://example.org/light"],
            "covered_aspects": [RequiredAspect.light_exposure.value, "off_aspect"],
            "confidence": 0.9,
        },
        {
            "claim": "Semantically bound paraphrase",
            "evidence_quote": "This paraphrased quote is not literally present on the page.",
            "source_urls": ["https://example.org/light"],
            "covered_aspects": [RequiredAspect.light_exposure.value],
            "confidence": 0.9,
        },
        {
            "claim": "Unsupported",
            "evidence_quote": "Unsupported",
            "source_urls": ["https://untrusted.invalid/post"],
            "covered_aspects": [RequiredAspect.light_exposure.value],
        },
        {
            "claim": "Rejected source",
            "evidence_quote": "Snippet text.",
            "source_urls": ["https://example.org/rejected"],
            "covered_aspects": [RequiredAspect.light_exposure.value],
            "confidence": 0.9,
        },
        {
            "claim": "Blank status source",
            "evidence_quote": "Snippet text.",
            "source_urls": ["https://example.org/blank"],
            "covered_aspects": [RequiredAspect.light_exposure.value],
            "confidence": 0.9,
        },
    ]

    accepted = _accepted_acquired_claims(
        support,
        pages_by_url={
            trusted_page.result.url: trusted_page,
            untrusted_page.result.url: untrusted_page,
            blank_status_page.result.url: blank_status_page,
        },
        allowed_aspects={RequiredAspect.light_exposure.value},
    )

    assert len(accepted) == 2
    assert all(claim.source_url == "https://example.org/light" for claim in accepted)
    assert accepted[0].supported_aspects == (RequiredAspect.light_exposure.value,)
    assert accepted[1].evidence_quote.startswith("This paraphrased quote")


def test_absent_or_invalid_source_status_never_enters_accepted_persistence_claims() -> None:
    for status in ("", "rejected", "pending_review", "untrusted"):
        page = TrustedPageEvidence(
            result=SearchResult(
                title="Strict",
                url="https://example.org/strict",
                snippet="Snippet text.",
                source_domain="example.org",
            ),
            content="Snippet text.",
        fetch_status="fetched",
            validation_status=status,
        )
        accepted = _accepted_acquired_claims(
            [
                {
                    "claim": "Claim",
                    "evidence_quote": "Snippet text.",
                    "source_urls": ["https://example.org/strict"],
                    "covered_aspects": [RequiredAspect.light_exposure.value],
                    "confidence": 0.9,
                }
            ],
            pages_by_url={page.result.url: page},
            allowed_aspects={RequiredAspect.light_exposure.value},
        )
        assert accepted == [], status


def test_bounded_evidence_sources_keep_two_supplied_sources_separate_in_judge_input() -> None:
    from app.assistant.semantic_coverage import SemanticEvidence, SemanticSourceEvidence
    from app.enrichment.service import _bounded_evidence_sources

    local = SemanticEvidence(
        sources=(
            SemanticSourceEvidence(
                text="Local watering guidance text.",
                metadata={
                    "url": "https://example.org/watering",
                    "validation_status": "trusted",
                },
            ),
            SemanticSourceEvidence(
                text="Local light guidance text.",
                metadata={
                    "url": "https://example.org/light",
                    "validation_status": "trusted",
                },
            ),
        )
    )

    sources = _bounded_evidence_sources(local, None)

    assert [entry["url"] for entry in sources] == [
        "https://example.org/watering",
        "https://example.org/light",
    ]
    assert sources[0]["text"] == "Local watering guidance text."
    assert sources[1]["text"] == "Local light guidance text."
    assert sources[0]["validation_status"] == "trusted"
    assert sources[1]["validation_status"] == "trusted"
    assert sources[0]["source_package_id"] == "source-0"
    assert sources[1]["source_package_id"] == "source-1"


def test_bounded_evidence_sources_keep_two_same_url_packages_in_judge_input() -> None:
    from app.assistant.semantic_coverage import SemanticEvidence, SemanticSourceEvidence
    from app.enrichment.service import _bounded_evidence_sources

    local = SemanticEvidence(
        sources=(
            SemanticSourceEvidence(
                text="First package text.",
                metadata={
                    "url": "https://example.org/shared",
                    "validation_status": "trusted",
                },
            ),
            SemanticSourceEvidence(
                text="Second package text.",
                metadata={
                    "url": "https://example.org/shared",
                    "validation_status": "trusted",
                },
            ),
        )
    )

    sources = _bounded_evidence_sources(local, None)

    assert len(sources) == 2
    assert [entry["url"] for entry in sources] == [
        "https://example.org/shared",
        "https://example.org/shared",
    ]
    assert sources[0]["text"] == "First package text."
    assert sources[1]["text"] == "Second package text."
    assert sources[0]["source_package_id"] == "source-0"
    assert sources[1]["source_package_id"] == "source-1"


@pytest.mark.parametrize(
    ("urls", "id_suffix"),
    [
        (["", "https://example.org/light"], "blank-then-valid"),
        (["https://example.org/light", "https://example.org/light"], "duplicate"),
        (["https://example.org/light", "https://example.org/other"], "two-distinct"),
        ([], "empty"),
    ],
    ids=["blank-then-valid", "duplicate", "two-distinct", "empty"],
)
def test_accepted_acquired_claims_reject_non_singleton_raw_url_lists(
    urls: list[str], id_suffix: str
) -> None:
    page = TrustedPageEvidence(
        result=SearchResult(
            title="Light",
            url="https://example.org/light",
            snippet="Snippet text.",
            source_domain="example.org",
        ),
        content="Snippet text.",
        fetch_status="fetched",
        validation_status="trusted",
    )
    accepted = _accepted_acquired_claims(
        [
            {
                "claim": "Claim",
                "evidence_quote": "Snippet text.",
                "source_urls": urls,
                "covered_aspects": [RequiredAspect.light_exposure.value],
                "confidence": 0.9,
            }
        ],
        pages_by_url={page.result.url: page},
        allowed_aspects={RequiredAspect.light_exposure.value},
    )
    assert accepted == [], id_suffix


def test_accepted_acquired_claims_accept_only_a_singleton_raw_url_list() -> None:
    page = TrustedPageEvidence(
        result=SearchResult(
            title="Light",
            url="https://example.org/light",
            snippet="Bright indirect light is suitable.",
            source_domain="example.org",
        ),
        content="Bright indirect light is suitable.",
        fetch_status="fetched",
        validation_status="trusted",
    )
    accepted = _accepted_acquired_claims(
        [
            {
                "claim": "Use bright indirect light.",
                "evidence_quote": "Bright indirect light is suitable.",
                "source_urls": ["https://example.org/light"],
                "covered_aspects": [RequiredAspect.light_exposure.value],
                "confidence": 0.9,
            }
        ],
        pages_by_url={page.result.url: page},
        allowed_aspects={RequiredAspect.light_exposure.value},
    )
    assert len(accepted) == 1
    assert accepted[0].source_url == "https://example.org/light"



def test_bounded_evidence_sources_truncate_per_source_within_total_budget() -> None:
    from app.assistant.semantic_coverage import SemanticEvidence, SemanticSourceEvidence
    from app.enrichment.service import (
        MAX_JUDGE_EVIDENCE_CHARS,
        MAX_JUDGE_SOURCES,
        _bounded_evidence_sources,
    )

    long_text = "x" * (MAX_JUDGE_EVIDENCE_CHARS * 2)
    local = SemanticEvidence(
        sources=tuple(
            SemanticSourceEvidence(
                text=long_text,
                metadata={"url": f"https://example.org/source-{index}"},
            )
            for index in range(MAX_JUDGE_SOURCES + 5)
        )
    )

    sources = _bounded_evidence_sources(local, None)

    assert len(sources) == MAX_JUDGE_SOURCES
    assert all(len(entry["text"]) <= MAX_JUDGE_EVIDENCE_CHARS for entry in sources)
    assert sum(len(entry["text"]) for entry in sources) <= MAX_JUDGE_EVIDENCE_CHARS
    assert [entry["url"] for entry in sources] == [
        f"https://example.org/source-{index}" for index in range(MAX_JUDGE_SOURCES)
    ]


def test_support_citing_source_a_persists_only_source_a() -> None:
    page_a = TrustedPageEvidence(
        result=SearchResult(
            title="Source A",
            url="https://example.org/a",
            snippet="Snippet A.",
            source_domain="example.org",
        ),
        content="Snippet A.",
        fetch_status="fetched",
        validation_status="trusted",
    )
    page_b = TrustedPageEvidence(
        result=SearchResult(
            title="Source B",
            url="https://example.org/b",
            snippet="Snippet B.",
            source_domain="example.org",
        ),
        content="Snippet B.",
        fetch_status="fetched",
        validation_status="trusted",
    )
    accepted = _accepted_acquired_claims(
        [
            {
                "claim": "Bound to source A only.",
                "evidence_quote": "Snippet A.",
                "source_urls": ["https://example.org/a"],
                "covered_aspects": [RequiredAspect.light_exposure.value],
                "confidence": 0.9,
            },
            {
                "claim": "Bound to source B only.",
                "evidence_quote": "Snippet B.",
                "source_urls": ["https://example.org/b"],
                "covered_aspects": [RequiredAspect.light_exposure.value],
                "confidence": 0.9,
            },
        ],
        pages_by_url={
            page_a.result.url: page_a,
            page_b.result.url: page_b,
        },
        allowed_aspects={RequiredAspect.light_exposure.value},
    )

    assert [claim.source_url for claim in accepted] == [
        "https://example.org/a",
        "https://example.org/b",
    ]
    assert accepted[0].evidence_quote == "Snippet A."
    assert accepted[1].evidence_quote == "Snippet B."


def test_support_citing_two_urls_is_rejected_at_accepted_claim_selection() -> None:
    page_a = TrustedPageEvidence(
        result=SearchResult(
            title="Source A",
            url="https://example.org/a",
            snippet="Snippet A.",
            source_domain="example.org",
        ),
        content="Snippet A.",
        fetch_status="fetched",
        validation_status="trusted",
    )
    page_b = TrustedPageEvidence(
        result=SearchResult(
            title="Source B",
            url="https://example.org/b",
            snippet="Snippet B.",
            source_domain="example.org",
        ),
        content="Snippet B.",
        fetch_status="fetched",
        validation_status="trusted",
    )
    accepted = _accepted_acquired_claims(
        [
            {
                "claim": "One claim bound to two sources.",
                "evidence_quote": "Snippet A.",
                "source_urls": ["https://example.org/a", "https://example.org/b"],
                "covered_aspects": [RequiredAspect.light_exposure.value],
                "confidence": 0.9,
            }
        ],
        pages_by_url={
            page_a.result.url: page_a,
            page_b.result.url: page_b,
        },
        allowed_aspects={RequiredAspect.light_exposure.value},
    )

    assert accepted == []


def test_content_chunk_and_vector_identity_is_policy_and_aspect_set_independent() -> None:
    identity = CanonicalSpeciesIdentity(2878688, "Monstera deliciosa", True)
    claim = AcceptedEnrichmentClaim(
        claim="Use bright indirect light.",
        evidence_quote="Bright indirect light is suitable.",
        source_url="https://example.org/light",
        source_title="Light",
        source_domain="example.org",
        source_version="etag-v1",
        source_retrieved_at=datetime.now(UTC),
        source_published_at=None,
        supported_aspects=(RequiredAspect.light_exposure.value,),
        confidence=0.9,
    )
    metadata = EnrichmentEvidenceMetadata(
        canonical_species_key=identity.key,
        accepted_gbif_key=identity.accepted_gbif_key,
        normalized_binomial=identity.normalized_binomial or "",
        canonical_source_url=claim.source_url,
        canonical_source_domain=claim.source_domain,
        source_version=claim.source_version,
        normalized_content_hash="a" * 64,
        source_retrieved_at=claim.source_retrieved_at,
        enrichment_provenance={"kind": "confirmed_plant_enrichment"},
        taxonomy_provenance_id=uuid4(),
    )
    content_key = enrichment_content_key(metadata)

    assert stable_enrichment_document_id(content_key) == stable_enrichment_document_id(content_key)
    assert stable_enrichment_chunk_id(content_key, 0) == stable_enrichment_chunk_id(content_key, 0)
    assert "policy" not in content_key


class FakeSession:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


class FakeEvidenceRepository:
    def __init__(self) -> None:
        self.session = FakeSession()
        self.state = None
        self.support_calls: list[list[str]] = []

    async def get_enrichment_evidence_state(self, metadata):
        return self.state

    async def get_enrichment_evidence_state_by_document_id(
        self, document_id, *, for_update=False
    ):
        if self.state is None or self.state.document_id != document_id:
            return None
        return self.state

    async def add_enrichment_validation_evidence(
        self, *, validation_id, document_id
    ) -> None:
        self.evidence_associations = getattr(self, "evidence_associations", [])
        self.evidence_associations.append((validation_id, document_id))

    async def add_enrichment_aspect_supports(
        self, *, document_id, aspects, confidence, review_status
    ) -> None:
        self.support_calls.append(aspects)
        if self.state is not None:
            self.state = self.state.model_copy(
                update={
                    "chunks": [
                        chunk.model_copy(
                            update={
                                "metadata": {
                                    **chunk.metadata,
                                    "covered_aspects": list(
                                        dict.fromkeys(
                                            [
                                                *(chunk.metadata.get("covered_aspects") or []),
                                                *aspects,
                                            ]
                                        )
                                    ),
                                }
                            }
                        )
                        for chunk in self.state.chunks
                    ]
                }
            )


class FakeProgress:
    def __init__(self) -> None:
        self.persisted: list[list[str]] = []
        self.indexed: list[list[str]] = []

    async def record_persisted_aspects(self, *, job_id, persisted_aspects) -> None:
        self.persisted.append(list(persisted_aspects))

    async def record_indexed_aspects(self, *, job_id, indexed_aspects) -> None:
        self.indexed.append(list(indexed_aspects))


class FakeEvidenceIndex:
    def __init__(self, repository: FakeEvidenceRepository) -> None:
        self.repository = repository
        self.prepare_calls = 0
        self.persist_calls = 0
        self.index_calls = 0

    async def prepare_document(self, document, *, embedding_provider):
        from app.knowledge.rag import OrchestratedKnowledgeIngestion

        self.prepare_calls += 1
        source = document.sources[0]
        return OrchestratedKnowledgeIngestion(
            chunks=[
                KnowledgeChunk(
                    chunk_index=0,
                    content=document.content,
                    metadata=document.metadata,
                    scientific_name=document.scientific_name,
                    topic=document.topic,
                    source_domain=source.source_domain,
                    source_url=str(source.url),
                    confidence=document.confidence,
                    review_status=ReviewStatus.auto_ingested,
                    retrieved_at=source.retrieved_at,
                )
            ],
            embeddings=[[0.1]],
            provider="fake",
            model="fake",
        )

    async def persist_enrichment_relational(
        self, document, *, ingestion, enrichment, document_id
    ):
        self.persist_calls += 1
        chunks = [chunk.model_copy(update={"document_id": document_id}) for chunk in ingestion.chunks]
        self.repository.state = EnrichmentEvidenceState(
            document_id=document_id,
            chunks=chunks,
            embeddings=ingestion.embeddings,
            embedding_provider=ingestion.provider,
            embedding_model=ingestion.model,
        )
        return PersistedKnowledgeDocument(id=document_id, chunks=chunks)

    async def ensure_vector_nodes(self, **kwargs) -> None:
        self.index_calls += 1


@pytest.mark.asyncio
async def test_multi_aspect_evidence_is_embedded_once_and_reused_across_policy_contexts() -> None:
    repository = FakeEvidenceRepository()
    vector_index = FakeEvidenceIndex(repository)
    service = EnrichmentEvidencePersistenceService(
        repository,
        vector_index=vector_index,
        embedding_provider=object(),
    )
    claim = AcceptedEnrichmentClaim(
        claim="Use bright light and draining soil.",
        evidence_quote="Bright light and a draining substrate are recommended.",
        source_url="https://example.org/care",
        source_title="Care",
        source_domain="example.org",
        source_version="etag-v1",
        source_retrieved_at=datetime.now(UTC),
        source_published_at=None,
        supported_aspects=(
            RequiredAspect.light_exposure.value,
            RequiredAspect.soil_drainage.value,
        ),
        confidence=0.9,
    )
    identity = CanonicalSpeciesIdentity(2878688, "Monstera deliciosa", True)
    taxonomy_id = uuid4()
    job_id = uuid4()
    progress = FakeProgress()

    first = await service.persist_claim_relational(
        identity=identity,
        taxonomy_provenance_id=taxonomy_id,
        claim=claim,
        job_id=job_id,
        progress=progress,
    )
    await service.associate_validation_and_refresh(
        validation_id=uuid4(),
        document_id=first.document_id,
        job_id=job_id,
        progress=progress,
    )
    replay = await service.persist_claim_relational(
        identity=identity,
        taxonomy_provenance_id=taxonomy_id,
        claim=claim,
        job_id=job_id,
        progress=progress,
    )
    await service.associate_validation_and_refresh(
        validation_id=uuid4(),
        document_id=replay.document_id,
        job_id=job_id,
        progress=progress,
    )

    assert replay.document_id == first.document_id
    assert vector_index.prepare_calls == 1
    assert vector_index.persist_calls == 1
    assert vector_index.index_calls == 2
    assert repository.support_calls == [
        list(claim.supported_aspects),
        list(claim.supported_aspects),
    ]
    assert len(repository.evidence_associations) == 2


LIGHT = RequiredAspect.light_exposure
WATERING = RequiredAspect.watering_frequency_or_trigger
POLICY_REQUIRED = sorted(aspect.value for aspect in ENRICHMENT_POLICY_V1.required_aspects)


@pytest.mark.asyncio
async def test_progress_initialize_is_immutable_and_fails_closed(session_factory) -> None:
    async with session_factory() as session:
        progress = EnrichmentProgressRepository(session)
        job_id = uuid4()
        snapshot = await progress.initialize_or_load(
            job_id=job_id,
            policy_version=1,
            required_aspects=POLICY_REQUIRED,
        )
        assert set(snapshot.required_aspects) == set(POLICY_REQUIRED)

        with pytest.raises(ValueError, match="immutable"):
            await progress.initialize_or_load(
                job_id=job_id,
                policy_version=1,
                required_aspects=[LIGHT.value],
            )
        with pytest.raises(ValueError):
            await progress.initialize_or_load(
                job_id=job_id,
                policy_version=2,
                required_aspects=POLICY_REQUIRED,
            )
        with pytest.raises(ValueError):
            await progress.initialize_or_load(
                job_id=uuid4(),
                policy_version=999,
                required_aspects=[LIGHT.value],
            )
        with pytest.raises(ValueError):
            await progress.initialize_or_load(
                job_id=uuid4(),
                policy_version=1,
                required_aspects=["not_a_policy_aspect"],
            )
        await session.rollback()


@pytest.mark.asyncio
async def test_progress_records_validate_and_only_grow(session_factory) -> None:
    async with session_factory() as session:
        progress = EnrichmentProgressRepository(session)
        job_id = uuid4()
        await progress.initialize_or_load(
            job_id=job_id,
            policy_version=1,
            required_aspects=POLICY_REQUIRED,
        )
        await progress.record_local_coverage(
            job_id=job_id, local_covered_aspects=[LIGHT.value]
        )
        snapshot = await progress.record_persisted_aspects(
            job_id=job_id, persisted_aspects=[WATERING.value]
        )
        assert snapshot.persisted_covered_aspects == (WATERING.value,)
        snapshot = await progress.record_persisted_aspects(
            job_id=job_id, persisted_aspects=[LIGHT.value]
        )
        assert set(snapshot.persisted_covered_aspects) == {LIGHT.value, WATERING.value}
        assert snapshot.accepted_aspect_count == 2

        with pytest.raises(ValueError):
            await progress.record_persisted_aspects(
                job_id=job_id, persisted_aspects=["not_a_policy_aspect"]
            )

        snapshot = await progress.record_indexed_aspects(
            job_id=job_id, indexed_aspects=[WATERING.value]
        )
        assert snapshot.indexed_covered_aspects == (WATERING.value,)
        with pytest.raises(ValueError, match="subset"):
            await progress.record_indexed_aspects(
                job_id=job_id,
                indexed_aspects=[RequiredAspect.humidity_preference.value],
            )

        await progress.record_final_judging(
            job_id=job_id,
            final_covered_aspects=POLICY_REQUIRED,
            final_missing_aspects=[],
            answerability_status="full",
        )
        with pytest.raises(ValueError):
            await progress.record_final_judging(
                job_id=job_id,
                final_covered_aspects=[LIGHT.value],
                final_missing_aspects=[],
                answerability_status="full",
            )
        with pytest.raises(ValueError):
            await progress.record_final_judging(
                job_id=job_id,
                final_covered_aspects=[LIGHT.value],
                final_missing_aspects=[WATERING.value],
                answerability_status="mystery",
            )
        with pytest.raises(ValueError):
            await progress.record_acquisition_summary(
                job_id=job_id, acquisition_avoided=False, search_count=-1
            )
        await session.rollback()


def test_build_failure_terminal_result_partial_vs_failed() -> None:
    required = tuple(POLICY_REQUIRED)
    useful = EnrichmentJobProgress(
        job_id=uuid4(),
        policy_version=1,
        required_aspects=required,
        persisted_covered_aspects=(LIGHT.value,),
    )
    status, result, error = build_failure_terminal_result(
        useful,
        failure_category=JobFailureCategory.attempts_exhausted,
        operational_limitation=EnrichmentLimitation.retry_exhausted,
    )
    assert status is JobStatus.partial
    assert result is not None
    assert result.outcome == "partial"
    assert result.covered_aspects == [LIGHT.value]
    assert result.missing_aspects == [aspect for aspect in required if aspect != LIGHT.value]
    assert EnrichmentLimitation.missing_required_aspects in result.limitations
    assert EnrichmentLimitation.retry_exhausted in result.limitations
    assert error.category is JobFailureCategory.attempts_exhausted
    assert error.retryable is False

    empty = EnrichmentJobProgress(
        job_id=uuid4(), policy_version=1, required_aspects=required
    )
    status, result, error = build_failure_terminal_result(
        empty,
        failure_category=JobFailureCategory.attempts_exhausted,
        operational_limitation=EnrichmentLimitation.retry_exhausted,
    )
    assert status is JobStatus.failed
    assert result is None
    assert error.category is JobFailureCategory.attempts_exhausted

    status, result, error = build_failure_terminal_result(
        None,
        failure_category=JobFailureCategory.attempts_exhausted,
        operational_limitation=EnrichmentLimitation.retry_exhausted,
    )
    assert status is JobStatus.failed
    assert result is None


def test_build_failure_terminal_judge_only_coverage_is_failed() -> None:
    required = tuple(POLICY_REQUIRED)
    snapshot = EnrichmentJobProgress(
        job_id=uuid4(),
        policy_version=1,
        required_aspects=required,
        final_judged_covered_aspects=required,
        final_judged_missing_aspects=(),
        answerability_status="full",
    )
    status, result, error = build_failure_terminal_result(
        snapshot,
        failure_category=JobFailureCategory.attempts_exhausted,
        operational_limitation=EnrichmentLimitation.retry_exhausted,
    )
    assert status is JobStatus.failed
    assert result is None
    assert error.category is JobFailureCategory.attempts_exhausted


def test_build_failure_terminal_persisted_coverage_can_be_operational_partial() -> None:
    required = tuple(POLICY_REQUIRED)
    snapshot = EnrichmentJobProgress(
        job_id=uuid4(),
        policy_version=1,
        required_aspects=required,
        persisted_covered_aspects=required,
        final_judged_covered_aspects=required,
        final_judged_missing_aspects=(),
        answerability_status="full",
    )
    status, result, error = build_failure_terminal_result(
        snapshot,
        failure_category=JobFailureCategory.attempts_exhausted,
        operational_limitation=EnrichmentLimitation.indexing_deferred,
    )
    assert status is JobStatus.partial
    assert result is not None
    assert result.missing_aspects == []
    assert EnrichmentLimitation.missing_required_aspects not in result.limitations
    assert EnrichmentLimitation.indexing_deferred in result.limitations
    assert error.category is JobFailureCategory.attempts_exhausted


def test_build_efficacy_snapshot_reflects_durable_progress() -> None:
    snapshot = EnrichmentJobProgress(
        job_id=uuid4(),
        policy_version=1,
        required_aspects=tuple(POLICY_REQUIRED),
        local_covered_aspects=(LIGHT.value,),
        persisted_covered_aspects=(LIGHT.value, WATERING.value),
        acquisition_avoided=False,
        search_count=3,
        accepted_aspect_count=2,
    )
    efficacy = build_efficacy_snapshot(snapshot)
    assert efficacy.policy_version == 1
    assert efficacy.acquisition_avoided is False
    assert efficacy.local_covered_count == 1
    assert efficacy.final_covered_count == 2
    assert efficacy.coverage_gain == 1
    assert efficacy.accepted_aspect_count == 2
    assert efficacy.search_count == 3


class _FailingProgress:
    async def record_persisted_aspects(self, *, job_id, persisted_aspects) -> None:
        raise RuntimeError("progress checkpoint failure")

    async def record_indexed_aspects(self, *, job_id, indexed_aspects) -> None:
        raise RuntimeError("progress checkpoint failure")


@pytest.mark.asyncio
async def test_progress_failure_rolls_back_paired_evidence_transaction() -> None:
    repository = FakeEvidenceRepository()
    vector_index = FakeEvidenceIndex(repository)
    service = EnrichmentEvidencePersistenceService(
        repository,
        vector_index=vector_index,
        embedding_provider=object(),
    )
    claim = AcceptedEnrichmentClaim(
        claim="Use bright light and draining soil.",
        evidence_quote="Bright light and a draining substrate are recommended.",
        source_url="https://example.org/care",
        source_title="Care",
        source_domain="example.org",
        source_version="etag-v1",
        source_retrieved_at=datetime.now(UTC),
        source_published_at=None,
        supported_aspects=(LIGHT.value,),
        confidence=0.9,
    )
    identity = CanonicalSpeciesIdentity(2878688, "Monstera deliciosa", True)

    with pytest.raises(RuntimeError, match="progress checkpoint failure"):
        await service.persist_claim_relational(
            identity=identity,
            taxonomy_provenance_id=uuid4(),
            claim=claim,
            job_id=uuid4(),
            progress=_FailingProgress(),
        )

    assert repository.session.rollbacks >= 1
    assert repository.session.commits == 0


@pytest.mark.parametrize("fetch_status", ["not_fetched", "failed", "empty", "skipped"])
def test_snippet_only_pages_never_become_persistent_claims(fetch_status: str) -> None:
    page = TrustedPageEvidence(
        result=SearchResult(
            title="Snippet only",
            url="https://example.org/snippet",
            snippet="Strong snippet about light exposure.",
            source_domain="example.org",
        ),
        content=None,
        fetch_status=fetch_status,
        validation_status="trusted",
        snippet_length=len("Strong snippet about light exposure."),
    )
    accepted = _accepted_acquired_claims(
        [
            {
                "claim": "Snippet-backed claim.",
                "evidence_quote": "Strong snippet about light exposure.",
                "source_urls": ["https://example.org/snippet"],
                "covered_aspects": [RequiredAspect.light_exposure.value],
                "confidence": 0.9,
            }
        ],
        pages_by_url={page.result.url: page},
        allowed_aspects={RequiredAspect.light_exposure.value},
    )

    assert accepted == []


def test_unsafe_redirect_with_strong_snippet_has_zero_persistence_effects() -> None:
    """A fetch that fails to an unsafe destination with a strong snippet
    never produces fetched evidence, so no claim is accepted for it."""
    from app.enrichment.acquisition import OfflineEnrichmentAcquisitionService
    from app.enrichment.identity import CanonicalSpeciesIdentity

    page = TrustedPageEvidence(
        result=SearchResult(
            title="Unsafe",
            url="https://example.org/unsafe",
            snippet="Strong snippet.",
            source_domain="example.org",
        ),
        content=None,
        error="unsafe destination",
        fetch_status="failed",
        fetch_error_category="unsafe_destination",
        validation_status="trusted",
        snippet_length=14,
    )

    class _FailingFetcher:
        async def fetch_all(self, results, *, limit=3):
            return [page]

    service = OfflineEnrichmentAcquisitionService(
        search=_NoopSearch(),
        trusted_sources=TrustedSourceValidator(["example.org"]),
        page_fetcher=_FailingFetcher(),  # type: ignore[arg-type]
    )
    identity = CanonicalSpeciesIdentity(2878688, "Monstera deliciosa", True)
    required = tuple(RequiredAspect[aspect] for aspect in POLICY_REQUIRED)

    import asyncio

    result = asyncio.get_event_loop().run_until_complete(
        service.acquire(
            identity=identity,
            required_aspects=required,
            acquisition_aspects=[RequiredAspect.light_exposure],
            policy=ENRICHMENT_POLICY_V1,
        )
    )
    assert result.evidence == ()


class _NoopSearch:
    async def search(self, query, *, allowed_domains=None):
        return []
