from datetime import datetime, timezone
from uuid import uuid4

import pytest
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
from app.enrichment.service import EnrichmentExecution, _accepted_acquired_claims
from app.jobs.handler import HandlerRegistry
from app.jobs.handlers.enrich_confirmed_plant import EnrichConfirmedPlantHandler
from app.jobs.schemas import (
    EnrichConfirmedPlantPayload,
    EnrichmentJobResult,
    JobFailureCategory,
    JobStatus,
    JobType,
)
from app.knowledge.acquisition import TrustedSourceValidator
from app.knowledge.page_evidence import TrustedPageEvidence
from app.knowledge.schemas import EnrichmentEvidenceMetadata
from app.knowledge.schemas import (
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


def test_only_final_supported_trusted_acquired_claims_are_selected() -> None:
    trusted_page = TrustedPageEvidence(
        result=SearchResult(
            title="Trusted",
            url="https://example.org/light",
            snippet="Bright indirect light is suitable.",
            source_domain="example.org",
        ),
        content="Bright indirect light is suitable.",
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
            "claim": "Fabricated quote",
            "evidence_quote": "This text is absent from the trusted page.",
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
    ]

    accepted = _accepted_acquired_claims(
        support,
        pages_by_url={trusted_page.result.url: trusted_page},
        allowed_aspects={RequiredAspect.light_exposure.value},
    )

    assert len(accepted) == 1
    assert accepted[0].supported_aspects == (RequiredAspect.light_exposure.value,)


def test_content_chunk_and_vector_identity_is_policy_and_aspect_set_independent() -> None:
    identity = CanonicalSpeciesIdentity(2878688, "Monstera deliciosa", True)
    claim = AcceptedEnrichmentClaim(
        claim="Use bright indirect light.",
        evidence_quote="Bright indirect light is suitable.",
        source_url="https://example.org/light",
        source_title="Light",
        source_domain="example.org",
        source_version="etag-v1",
        source_retrieved_at=datetime.now(timezone.utc),
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

    async def commit(self) -> None:
        self.commits += 1


class FakeEvidenceRepository:
    def __init__(self) -> None:
        self.session = FakeSession()
        self.state = None
        self.support_calls: list[list[str]] = []

    async def get_enrichment_evidence_state(self, metadata):
        return self.state

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
        source_retrieved_at=datetime.now(timezone.utc),
        source_published_at=None,
        supported_aspects=(
            RequiredAspect.light_exposure.value,
            RequiredAspect.soil_drainage.value,
        ),
        confidence=0.9,
    )
    identity = CanonicalSpeciesIdentity(2878688, "Monstera deliciosa", True)
    taxonomy_id = uuid4()

    first = await service.persist_claim_relational(
        identity=identity,
        taxonomy_provenance_id=taxonomy_id,
        claim=claim,
    )
    await service.ensure_claim_indexed(first)
    replay = await service.persist_claim_relational(
        identity=identity,
        taxonomy_provenance_id=taxonomy_id,
        claim=claim,
    )
    await service.ensure_claim_indexed(replay)

    assert replay.document_id == first.document_id
    assert vector_index.prepare_calls == 1
    assert vector_index.persist_calls == 1
    assert vector_index.index_calls == 2
    assert repository.support_calls == [
        list(claim.supported_aspects),
        list(claim.supported_aspects),
    ]
