from datetime import UTC, datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.assistant.tools.ingestion import build_validated_claim_document
from app.assistant.tools.types import EXTERNAL_FALLBACK_EVIDENCE_CONFIDENCE
from app.auth.tables import (
    knowledge_chunks,
    knowledge_documents,
    knowledge_embeddings,
    knowledge_sources,
)
from app.knowledge.acquisition import KnowledgeAcquisitionService, TrustedSourceValidator
from app.knowledge.page_evidence import TrustedPageEvidence, TrustedPageEvidenceFetcher
from app.knowledge.rag import (
    AppEmbeddingTransform,
    KnowledgeVectorIndex,
    LlamaIndexRuntime,
    OrchestratedKnowledgeIngestion,
    PrecomputedEmbeddingOnly,
    build_llamaindex_metadata_filters,
    build_metadata_filter_specs,
)
from app.knowledge.rag.runtime import VectorIndexError, _llamaindex_chunk_metadata
from app.knowledge.repository import KnowledgeRepository
from app.knowledge.schemas import (
    AcquisitionStatus,
    KnowledgeChunk,
    KnowledgeDocumentInput,
    KnowledgeRetrievalFilters,
    KnowledgeSourceInput,
    ReviewStatus,
)
from app.providers.types import EmbeddingResult, JsonGenerationResult, SearchResult


class FakeHeaders:
    def __init__(self, content_type: str, charset: str | None = "utf-8") -> None:
        self.content_type = content_type
        self.charset = charset

    def get_content_type(self) -> str:
        return self.content_type

    def get_content_charset(self) -> str | None:
        return self.charset


class FakePageResponse:
    def __init__(self, *, url: str, body: bytes, content_type: str = "text/html") -> None:
        self.url = url
        self.body = body
        self.headers = FakeHeaders(content_type)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def geturl(self) -> str:
        return self.url

    def read(self, size: int) -> bytes:
        return self.body[:size]


class FakePageOpener:
    def __init__(self, response: FakePageResponse) -> None:
        self.response = response
        self.requests = []

    def open(self, request, *, timeout: int):
        self.requests.append((request, timeout))
        return self.response


class FakeLlamaRuntime:
    def __init__(self) -> None:
        self.indexed_chunks = []
        self.index_calls = 0
        self.ingest_calls = 0
        self.retrieve_calls = 0

    async def orchestrate_ingestion(self, *, document, embedding_provider):
        self.ingest_calls += 1
        source = document.sources[0]
        retrieved_at = source.retrieved_at
        metadata = {
            "species_id": str(document.species_id) if document.species_id else None,
            "scientific_name": document.scientific_name,
            "topic": document.topic,
            "source_domain": source.source_domain,
            "source_url": str(source.url),
            "confidence": document.confidence,
            "review_status": document.review_status.value,
            "retrieved_at": retrieved_at.isoformat(),
            "created_at": retrieved_at.isoformat(),
        }
        chunk = KnowledgeChunk(
            chunk_index=0,
            content=document.content,
            metadata=metadata,
            species_id=document.species_id,
            scientific_name=document.scientific_name,
            topic=document.topic,
            source_domain=source.source_domain,
            source_url=str(source.url),
            confidence=document.confidence,
            review_status=document.review_status,
            retrieved_at=retrieved_at,
            created_at=retrieved_at,
        )
        return OrchestratedKnowledgeIngestion(
            chunks=[chunk],
            embeddings=[[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]],
            provider="fake-llamaindex",
            model="fake-llamaindex-embedding",
        )

    async def index_chunks(self, *, chunks, embeddings, provider, model) -> None:
        self.index_calls += 1
        self.indexed_chunks = list(chunks)

    async def ensure_nodes(self, *, chunks, embeddings, provider, model) -> None:
        await self.index_chunks(
            chunks=chunks,
            embeddings=embeddings,
            provider=provider,
            model=model,
        )

    async def has_all_nodes(self, node_ids) -> bool:
        return set(node_ids) == {chunk.id for chunk in self.indexed_chunks}

    async def retrieve_nodes(self, *, filters, query_text, query_embedding, limit):
        self.retrieve_calls += 1
        return [FakeRetrievedNode(chunk.id, 1.0) for chunk in self.indexed_chunks[:limit]]


class FailingLlamaRuntime(FakeLlamaRuntime):
    async def retrieve_nodes(self, *, filters, query_text, query_embedding, limit):
        raise VectorIndexError("pgvector unavailable")


class FailingIngestionRuntime(FakeLlamaRuntime):
    async def orchestrate_ingestion(self, *, document, embedding_provider):
        raise RuntimeError("LlamaIndex ingestion unavailable")


class FakeRetrievedNode:
    def __init__(self, chunk_id: UUID, score: float) -> None:
        self.chunk_id = chunk_id
        self.score = score


def _validated_claim(*, source_provenance: str, confidence: float = 0.9) -> dict[str, object]:
    return {
        "scientific_name": "Cotyledon tomentosa",
        "topic": "watering",
        "source_url": "https://example.org/watering",
        "source_domain": "example.org",
        "source_title": "Watering guide",
        "source_provenance": source_provenance,
        "claim": "Water when the substrate dries.",
        "evidence_quote": "Allow the substrate to dry before watering.",
        "confidence": confidence,
        "covered_aspects": ["watering_frequency_or_trigger"],
        "required_aspects": ["watering_frequency_or_trigger"],
        "missing_aspects": [],
        "answerability_status": "full",
        "language": "en",
    }


def test_validated_claim_document_caps_external_fallback_confidence() -> None:
    trusted = build_validated_claim_document(
        claim=_validated_claim(source_provenance="trusted")
    )
    external = build_validated_claim_document(
        claim=_validated_claim(source_provenance="external_fallback")
    )

    assert trusted is not None
    assert external is not None
    assert trusted.confidence == 0.9
    assert external.confidence == EXTERNAL_FALLBACK_EVIDENCE_CONFIDENCE
    assert external.confidence < trusted.confidence
    assert trusted.sources[0].validation_status == "trusted"
    assert external.sources[0].validation_status == "external_fallback"


def test_llamaindex_chunk_metadata_preserves_validated_claim_fields() -> None:
    now = datetime.now(UTC)
    chunk = KnowledgeChunk(
        id=UUID("0d10f30c-7859-4f3c-b7d3-1c5999f640c8"),
        chunk_index=0,
        content="Water when the substrate dries.",
        metadata={
            "covered_aspects": ["watering_frequency_or_trigger"],
            "required_aspects": ["watering_frequency_or_trigger"],
            "evidence_type": "validated_web_claim",
            "answerability_status": "full",
            "source_provenance": "external_fallback",
            "scientific_name": "must not override canonical fields",
        },
        scientific_name="Cotyledon tomentosa",
        topic="watering",
        source_domain="example.org",
        source_url="https://example.org/watering",
        confidence=EXTERNAL_FALLBACK_EVIDENCE_CONFIDENCE,
        review_status=ReviewStatus.auto_ingested,
        retrieved_at=now,
        created_at=now,
    )

    metadata = _llamaindex_chunk_metadata(
        chunk,
        provider="test-provider",
        model="test-model",
        embedding_dimension=8,
    )

    assert metadata["scientific_name"] == "Cotyledon tomentosa"
    assert metadata["covered_aspects"] == ["watering_frequency_or_trigger"]
    assert metadata["required_aspects"] == ["watering_frequency_or_trigger"]
    assert metadata["evidence_type"] == "validated_web_claim"
    assert metadata["answerability_status"] == "full"
    assert metadata["source_domain"] == "example.org"
    assert metadata["source_provenance"] == "external_fallback"
    assert metadata["embedding_provider"] == "test-provider"
    assert metadata["embedding_model"] == "test-model"
    assert metadata["embedding_dimension"] == 8


class RecordingEmbeddingProvider:
    def __init__(self) -> None:
        self.calls = []

    async def create_embeddings(self, texts: list[str], **kwargs) -> EmbeddingResult:
        self.calls.append((texts, kwargs))
        return EmbeddingResult(
            provider="recording",
            model="recording-model",
            embeddings=[[float(index + 1)] for index, _ in enumerate(texts)],
        )


class RecordingJsonModelProvider:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    async def generate_json(self, prompt: str, schema: dict, **kwargs) -> JsonGenerationResult:
        self.prompts.append(prompt)
        return JsonGenerationResult(
            provider="recording",
            model="recording-model",
            data={"title": "Recorded", "content": "Recorded content.", "confidence": 0.7},
        )


class FakeSearchProvider:
    def __init__(self, results: list[SearchResult] | None = None) -> None:
        self.results = results if results is not None else [_search_result()]

    async def search(self, query: str, **kwargs) -> list[SearchResult]:
        return self.results


def _providers(
    *,
    model: RecordingJsonModelProvider | None = None,
    search_results: list[SearchResult] | None = None,
):
    return SimpleNamespace(
        model=model or RecordingJsonModelProvider(),
        search=FakeSearchProvider(search_results),
        embeddings=RecordingEmbeddingProvider(),
    )


class FakeTransformComponent:
    pass


class FakeMetadataMode:
    NONE = "none"


class FakeNode:
    def __init__(self, text: str, metadata: dict[str, object]) -> None:
        self.text = text
        self.metadata = metadata
        self.embedding = None

    def get_content(self, *, metadata_mode):
        assert metadata_mode == FakeMetadataMode.NONE
        return self.text


class NoSqlVectorRepository(KnowledgeRepository):
    async def retrieve_chunks(self, *args, **kwargs):
        raise AssertionError("runtime retrieval must not use SQL-only repository retrieval")


class RecordingRollbackRepository(KnowledgeRepository):
    def __init__(self, session) -> None:
        super().__init__(session)
        self.rollback_calls = 0

    async def rollback(self) -> None:
        self.rollback_calls += 1
        await super().rollback()


@pytest.mark.asyncio
async def test_knowledge_document_persists_chunks_sources_and_embeddings(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        repository = KnowledgeRepository(session)
        persisted = await repository.save_document(_document())
        await repository.add_embeddings(
            chunks=persisted.chunks,
            embeddings=[[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]],
            provider="test",
            model="test-embedding",
        )

        documents = (await session.execute(select(knowledge_documents))).all()
        sources = (await session.execute(select(knowledge_sources))).all()
        chunks = (await session.execute(select(knowledge_chunks))).all()
        embeddings = (await session.execute(select(knowledge_embeddings))).all()

    assert len(documents) == 1
    assert len(sources) == 1
    assert len(chunks) == 1
    assert len(embeddings) == 1
    assert chunks[0].metadata["scientific_name"] == "Cotyledon tomentosa"
    assert chunks[0].metadata["review_status"] == "auto_ingested"
    assert embeddings[0].embedding_dimension == 8


@pytest.mark.asyncio
async def test_add_embeddings_rejects_wrong_dimension_before_insert(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        repository = KnowledgeRepository(session)
        persisted = await repository.save_document(_document())

        with pytest.raises(ValueError, match="expected 8, got 3"):
            await repository.add_embeddings(
                chunks=persisted.chunks,
                embeddings=[[0.1, 0.2, 0.3]],
                provider="test",
                model="wrong-dimension",
            )

        embeddings = (await session.execute(select(knowledge_embeddings))).all()

    assert embeddings == []


@pytest.mark.asyncio
async def test_retrieval_filters_by_metadata_and_orders_by_embedding_score(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        repository = KnowledgeRepository(session)
        persisted = await repository.save_document(_document(topic="watering"))
        await repository.add_embeddings(
            chunks=persisted.chunks,
            embeddings=[[1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]],
            provider="test",
            model=None,
        )

        matched = await repository.retrieve_chunks(
            KnowledgeRetrievalFilters(
                scientific_name="Cotyledon tomentosa",
                topic="watering",
                source_domain="example.org",
                min_confidence=0.8,
                review_status=ReviewStatus.auto_ingested,
            ),
            query_embedding=[1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        )
        missed = await repository.retrieve_chunks(
            KnowledgeRetrievalFilters(scientific_name="Monstera deliciosa", topic="watering")
        )

    assert len(matched) == 1
    assert matched[0].score == 1.0
    assert missed == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("filter_name", "filter_value", "expected_provenance"),
    [
        ("source_provenance", "trusted", "trusted"),
        ("source_provenance", "external_fallback", "external_fallback"),
        ("answerability_status", "full", "trusted"),
        ("answerability_status", "partial", "external_fallback"),
    ],
)
async def test_relational_retrieval_filters_validated_claim_metadata(
    session_factory: async_sessionmaker[AsyncSession],
    filter_name: str,
    filter_value: str,
    expected_provenance: str,
) -> None:
    async with session_factory() as session:
        repository = KnowledgeRepository(session)
        for provenance, answerability in (
            ("trusted", "full"),
            ("external_fallback", "partial"),
        ):
            document = _document(topic="watering").model_copy(
                update={
                    "title": f"{provenance} guidance",
                    "metadata": {
                        "covered_aspects": ["watering_frequency_or_trigger"],
                        "evidence_type": "validated_web_claim",
                        "source_provenance": provenance,
                        "answerability_status": answerability,
                    },
                }
            )
            await repository.save_document(document)

        filters = KnowledgeRetrievalFilters.model_validate(
            {
                "topic": "watering",
                "covered_aspect": "watering_frequency_or_trigger",
                filter_name: filter_value,
            }
        )
        matched = await repository.retrieve_chunks(filters, limit=20)

    assert matched
    assert {chunk.metadata["source_provenance"] for chunk in matched} == {
        expected_provenance
    }
    expected_answerability = "full" if expected_provenance == "trusted" else "partial"
    assert {chunk.metadata["answerability_status"] for chunk in matched} == {
        expected_answerability
    }


@pytest.mark.asyncio
async def test_acquisition_uses_trusted_sources_embeds_and_retrieves(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        repository = KnowledgeRepository(session)
        runtime = FakeLlamaRuntime()
        service = KnowledgeAcquisitionService(
            repository,
            providers=_providers(),
            trusted_sources=TrustedSourceValidator(["example.org"]),
            vector_index=KnowledgeVectorIndex(repository, runtime=runtime),
        )
        result = await service.retrieve_or_acquire(
            scientific_name="Cotyledon tomentosa",
            topic="watering",
        )

    assert result.status == AcquisitionStatus.acquired
    assert result.document_id is not None
    assert result.chunks
    assert result.chunks[0].review_status == ReviewStatus.auto_ingested
    assert runtime.ingest_calls == 1
    assert runtime.retrieve_calls == 2
    assert runtime.index_calls == 1


@pytest.mark.asyncio
async def test_enrichment_retrieval_orders_chunks_by_requested_aspects(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """`_retrieve_enrichment_chunks` issues one vector query per distinct
    requested aspect and orders the deduplicated result by the requested order,
    not by retrieval score."""
    from app.enrichment.identity import CanonicalSpeciesIdentity
    from app.knowledge.schemas import KnowledgeRetrievalFilters

    aspect_a = "watering_frequency_or_trigger"
    aspect_b = "light_exposure"
    async with session_factory() as session:
        repository = KnowledgeRepository(session)
        _, chunk_a_id = await _persist_enrichment_chunk(
            session, aspect=aspect_a, content="Aspect A evidence content."
        )
        _, chunk_b_id = await _persist_enrichment_chunk(
            session, aspect=aspect_b, content="Aspect B evidence content."
        )
        await session.commit()

        class AspectOrderedRuntime(FakeLlamaRuntime):
            def __init__(self) -> None:
                super().__init__()
                self.aspect_queries: list[str] = []

            async def retrieve_nodes(
                self, *, filters, query_text, query_embedding, limit
            ):
                self.retrieve_calls += 1
                self.aspect_queries.append(filters.covered_aspect)
                if filters.covered_aspect == aspect_a:
                    return [FakeRetrievedNode(chunk_a_id, 0.5)]
                if filters.covered_aspect == aspect_b:
                    return [FakeRetrievedNode(chunk_b_id, 0.4)]
                return []

        runtime = AspectOrderedRuntime()
        identity = CanonicalSpeciesIdentity(
            accepted_gbif_key=1,
            normalized_binomial="Cotyledon tomentosa",
            taxonomy_validated=True,
        )
        service = KnowledgeAcquisitionService(
            repository,
            providers=SimpleNamespace(
                model=RecordingJsonModelProvider(),
                search=FakeSearchProvider([]),
                embeddings=RecordingEmbeddingProvider(),
            ),
            trusted_sources=TrustedSourceValidator(["example.org"]),
            vector_index=KnowledgeVectorIndex(repository, runtime=runtime),
        )
        result = await service._retrieve_enrichment_chunks(
            scientific_name=identity.normalized_binomial,
            topic="confirmed_plant_enrichment",
            canonical_species_key=identity.key,
            accepted_gbif_key=1,
            required_aspects=[aspect_b, aspect_a],
            question="care",
        )

    assert [chunk.id for chunk in result] == [chunk_b_id, chunk_a_id]
    assert runtime.retrieve_calls == 2
    assert runtime.aspect_queries == [aspect_b, aspect_a]


async def _persist_enrichment_chunk(
    session: AsyncSession, *, aspect: str, content: str
) -> tuple[UUID, UUID]:
    """Persist one enrichment chunk supporting a single aspect with a full
    validation run so `get_chunks_by_ids` attaches `validation_provenance`.
    Returns (document_id, chunk_id)."""
    from uuid import uuid4

    import hashlib

    from app.enrichment.evidence import stable_enrichment_document_id
    from app.enrichment.identity import CanonicalSpeciesIdentity
    from app.knowledge.schemas import EnrichmentEvidenceMetadata, ReviewStatus

    identity = CanonicalSpeciesIdentity(
        accepted_gbif_key=1,
        normalized_binomial="Cotyledon tomentosa",
        taxonomy_validated=True,
    )
    now = datetime.now(UTC)
    taxonomy_id = uuid4()
    job_id = uuid4()
    doc_id = stable_enrichment_document_id(f"fixture-{aspect}-content-key")
    chunk_id = uuid4()
    validation_run_id = uuid4()
    metadata = EnrichmentEvidenceMetadata(
        canonical_species_key=identity.key,
        accepted_gbif_key=identity.accepted_gbif_key,
        normalized_binomial=identity.normalized_binomial,
        canonical_source_url="https://example.org/care",
        canonical_source_domain="example.org",
        source_version="etag-v1",
        normalized_content_hash=hashlib.sha256(aspect.encode()).hexdigest(),
        source_retrieved_at=now,
        enrichment_provenance={"kind": "confirmed_plant_enrichment", "version": 1},
        taxonomy_provenance_id=taxonomy_id,
    )
    document = KnowledgeDocumentInput(
        scientific_name=identity.normalized_binomial,
        topic="confirmed_plant_enrichment",
        title="Care evidence",
        content=content,
        confidence=0.9,
        review_status=ReviewStatus.auto_ingested,
        sources=[
            KnowledgeSourceInput(
                title="Care evidence",
                url="https://example.org/care",
                source_domain="example.org",
                retrieved_at=now,
                validation_status="trusted",
            )
        ],
        metadata={
            "covered_aspects": [aspect],
            "evidence_type": "confirmed_plant_enrichment",
            "source_provenance": "trusted",
            "canonical_species_key": identity.key,
        },
    )
    chunk = KnowledgeChunk(
        id=chunk_id,
        document_id=doc_id,
        chunk_index=0,
        content=content,
        metadata=document.metadata,
        scientific_name=identity.normalized_binomial,
        topic=document.topic,
        source_domain="example.org",
        source_url="https://example.org/care",
        confidence=0.9,
        review_status=ReviewStatus.auto_ingested,
        retrieved_at=now,
    )
    repository = KnowledgeRepository(session)
    await repository.save_document(
        document,
        chunks=[chunk],
        commit=False,
        document_id=doc_id,
        enrichment=metadata,
    )
    await repository.add_enrichment_aspect_supports(
        document_id=doc_id,
        aspects=[aspect],
        confidence=0.9,
        review_status=ReviewStatus.auto_ingested,
    )
    await repository.add_enrichment_validation_run(
        validation_id=validation_run_id,
        job_id=job_id,
        taxonomy_provenance_id=taxonomy_id,
        policy_version=1,
        required_aspects=[aspect],
        covered_aspects=[aspect],
        missing_aspects=[],
        answerability_status="full",
        judge_confidence=0.9,
        validation_metadata={"acquisition_avoided": False},
    )
    await repository.add_enrichment_validation_evidence(
        validation_id=validation_run_id,
        document_id=doc_id,
    )
    return doc_id, chunk_id


@pytest.mark.asyncio
async def test_enrichment_retrieval_filters_aspect_before_pgvector_top_k(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """A requested-aspect chunk must not be displaced by 24 higher-scoring
    unrelated chunks: aspect filtering happens before the pgvector top-k."""
    from uuid import uuid4

    from app.auth.tables import knowledge_document_aspect_supports
    from app.enrichment.evidence import enrichment_content_key, stable_enrichment_document_id
    from app.enrichment.identity import CanonicalSpeciesIdentity
    from app.knowledge.schemas import (
        EnrichmentEvidenceMetadata,
        ReviewStatus,
    )

    identity = CanonicalSpeciesIdentity(
        accepted_gbif_key=1,
        normalized_binomial="Cotyledon tomentosa",
        taxonomy_validated=True,
    )
    now = datetime.now(UTC)
    taxonomy_id = uuid4()
    job_id = uuid4()
    doc_id = stable_enrichment_document_id("fixture-content-key")
    chunk_id = uuid4()
    aspect_watering = "watering_frequency_or_trigger"
    aspect_light = "light_exposure"

    async with session_factory() as session:
        repository = KnowledgeRepository(session)
        validation_run_id = uuid4()
        metadata = EnrichmentEvidenceMetadata(
            canonical_species_key=identity.key,
            accepted_gbif_key=identity.accepted_gbif_key,
            normalized_binomial=identity.normalized_binomial,
            canonical_source_url="https://example.org/care",
            canonical_source_domain="example.org",
            source_version="etag-v1",
            normalized_content_hash="a" * 64,
            source_retrieved_at=now,
            enrichment_provenance={"kind": "confirmed_plant_enrichment", "version": 1},
            taxonomy_provenance_id=taxonomy_id,
        )
        document = KnowledgeDocumentInput(
            scientific_name=identity.normalized_binomial,
            topic="confirmed_plant_enrichment",
            title="Care evidence",
            content="Requested aspect evidence content.",
            confidence=0.9,
            review_status=ReviewStatus.auto_ingested,
            sources=[
                KnowledgeSourceInput(
                    title="Care evidence",
                    url="https://example.org/care",
                    source_domain="example.org",
                    retrieved_at=now,
                    validation_status="trusted",
                )
            ],
            metadata={
                "covered_aspects": [aspect_watering, aspect_light],
                "evidence_type": "confirmed_plant_enrichment",
                "source_provenance": "trusted",
                "canonical_species_key": identity.key,
            },
        )
        chunk = KnowledgeChunk(
            id=chunk_id,
            document_id=doc_id,
            chunk_index=0,
            content="Requested aspect evidence content.",
            metadata=document.metadata,
            scientific_name=identity.normalized_binomial,
            topic=document.topic,
            source_domain="example.org",
            source_url="https://example.org/care",
            confidence=0.9,
            review_status=ReviewStatus.auto_ingested,
            retrieved_at=now,
        )
        await repository.save_document(
            document,
            chunks=[chunk],
            commit=False,
            document_id=doc_id,
            enrichment=metadata,
        )
        await repository.add_enrichment_aspect_supports(
            document_id=doc_id,
            aspects=[aspect_watering, aspect_light],
            confidence=0.9,
            review_status=ReviewStatus.auto_ingested,
        )
        await repository.add_enrichment_validation_run(
            validation_id=validation_run_id,
            job_id=job_id,
            taxonomy_provenance_id=taxonomy_id,
            policy_version=1,
            required_aspects=[aspect_watering, aspect_light],
            covered_aspects=[aspect_watering, aspect_light],
            missing_aspects=[],
            answerability_status="full",
            judge_confidence=0.9,
            validation_metadata={"acquisition_avoided": False},
        )
        await repository.add_enrichment_validation_evidence(
            validation_id=validation_run_id,
            document_id=doc_id,
        )
        await session.commit()

        class AspectFilteredRuntime(FakeLlamaRuntime):
            def __init__(self) -> None:
                super().__init__()
                self.seen_filters: list[KnowledgeRetrievalFilters] = []
                self.unrelated_ids = [uuid4() for _ in range(24)]

            async def retrieve_nodes(self, *, filters, query_text, query_embedding, limit):
                self.retrieve_calls += 1
                self.seen_filters.append(filters)
                if filters.covered_aspect:
                    return [FakeRetrievedNode(chunk_id, 0.3)]
                return [FakeRetrievedNode(nid, 0.9) for nid in self.unrelated_ids]

        class CountingSearchProvider(FakeSearchProvider):
            def __init__(self) -> None:
                super().__init__([])
                self.calls = 0

            async def search(self, query: str, **kwargs) -> list[SearchResult]:
                self.calls += 1
                return []

        runtime = AspectFilteredRuntime()
        search = CountingSearchProvider()
        service = KnowledgeAcquisitionService(
            repository,
            providers=SimpleNamespace(
                model=RecordingJsonModelProvider(),
                search=search,
                embeddings=RecordingEmbeddingProvider(),
            ),
            trusted_sources=TrustedSourceValidator(["example.org"]),
            vector_index=KnowledgeVectorIndex(repository, runtime=runtime),
        )
        result = await service.retrieve_or_acquire(
            scientific_name=identity.normalized_binomial,
            topic="confirmed_plant_enrichment",
            canonical_species_key=identity.key,
            accepted_gbif_key=1,
            required_aspects=[aspect_watering, aspect_light],
            question="watering",
        )

    assert result.status == AcquisitionStatus.retrieved
    assert [chunk.id for chunk in result.chunks] == [chunk_id]
    assert search.calls == 0
    aspect_queries = [filters for filters in runtime.seen_filters if filters.covered_aspect]
    assert len(aspect_queries) == 2
    assert {filters.covered_aspect for filters in aspect_queries} == {
        aspect_watering,
        aspect_light,
    }
    assert all(filters.evidence_type == "confirmed_plant_enrichment" for filters in aspect_queries)


@pytest.mark.asyncio
async def test_acquisition_generate_json_prompt_explicitly_requests_json(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        model = RecordingJsonModelProvider()
        service = KnowledgeAcquisitionService(
            KnowledgeRepository(session),
            providers=_providers(model=model),
            vector_index=KnowledgeVectorIndex(KnowledgeRepository(session), runtime=FakeLlamaRuntime()),
        )

        await service._generate_document(
            "Cotyledon tomentosa",
            "watering",
            [_search_result(snippet="Water when the substrate dries.")],
        )

    assert model.prompts
    assert "json" in model.prompts[0].casefold()


@pytest.mark.asyncio
async def test_acquisition_degrades_when_no_trusted_source_is_available(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        repository = KnowledgeRepository(session)
        service = KnowledgeAcquisitionService(
            repository,
            providers=_providers(),
            trusted_sources=TrustedSourceValidator(["gbif.org"]),
            vector_index=KnowledgeVectorIndex(repository, runtime=FakeLlamaRuntime()),
        )
        result = await service.retrieve_or_acquire(
            scientific_name="Cotyledon tomentosa",
            topic="watering",
        )

    assert result.status == AcquisitionStatus.degraded
    assert result.retry_available is True
    assert result.manual_search_url is not None
    assert "trusted" in result.limitations[0]


@pytest.mark.asyncio
async def test_acquisition_degrades_when_llamaindex_retrieval_fails(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        repository = KnowledgeRepository(session)
        service = KnowledgeAcquisitionService(
            repository,
            providers=_providers(),
            trusted_sources=TrustedSourceValidator(["example.org"]),
            vector_index=KnowledgeVectorIndex(repository, runtime=FailingLlamaRuntime()),
        )
        result = await service.retrieve_or_acquire(
            scientific_name="Cotyledon tomentosa",
            topic="watering",
        )

    assert result.status == AcquisitionStatus.degraded
    assert result.retry_available is True
    assert "LlamaIndex" in result.limitations[0]


@pytest.mark.asyncio
async def test_acquisition_degrades_when_llamaindex_ingestion_fails(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        repository = RecordingRollbackRepository(session)
        service = KnowledgeAcquisitionService(
            repository,
            providers=_providers(),
            trusted_sources=TrustedSourceValidator(["example.org"]),
            vector_index=KnowledgeVectorIndex(repository, runtime=FailingIngestionRuntime()),
        )
        result = await service.retrieve_or_acquire(
            scientific_name="Cotyledon tomentosa",
            topic="watering",
        )

    assert result.status == AcquisitionStatus.degraded
    assert result.retry_available is True
    assert "Trusted acquisition failed" in result.limitations[0]
    assert repository.rollback_calls == 1


@pytest.mark.asyncio
async def test_acquisition_does_not_use_sql_only_retrieval_path(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        repository = NoSqlVectorRepository(session)
        runtime = FakeLlamaRuntime()
        service = KnowledgeAcquisitionService(
            repository,
            providers=_providers(),
            trusted_sources=TrustedSourceValidator(["example.org"]),
            vector_index=KnowledgeVectorIndex(repository, runtime=runtime),
        )
        result = await service.retrieve_or_acquire(
            scientific_name="Cotyledon tomentosa",
            topic="watering",
        )

    assert result.status == AcquisitionStatus.acquired
    assert runtime.retrieve_calls == 2


@pytest.mark.asyncio
async def test_acquisition_uses_llamaindex_ingestion_instead_of_custom_chunking(
    session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_custom_chunking(*args, **kwargs):
        raise AssertionError("successful acquisition must use LlamaIndex ingestion")

    monkeypatch.setattr("app.knowledge.repository.chunk_document", fail_custom_chunking)
    async with session_factory() as session:
        repository = KnowledgeRepository(session)
        runtime = FakeLlamaRuntime()
        service = KnowledgeAcquisitionService(
            repository,
            providers=_providers(),
            trusted_sources=TrustedSourceValidator(["example.org"]),
            vector_index=KnowledgeVectorIndex(repository, runtime=runtime),
        )
        result = await service.retrieve_or_acquire(
            scientific_name="Cotyledon tomentosa",
            topic="watering",
        )

    assert result.status == AcquisitionStatus.acquired
    assert runtime.ingest_calls == 1


def test_llamaindex_metadata_filter_mapping_supports_all_retrieval_fields() -> None:
    retrieved_at = datetime(2026, 5, 1, tzinfo=UTC)
    created_at = datetime(2026, 5, 2, tzinfo=UTC)
    filters = KnowledgeRetrievalFilters(
        species_id=UUID("00000000-0000-0000-0000-000000000001"),
        scientific_name="Cotyledon tomentosa",
        topic="watering",
        source_domain="example.org",
        source_url="https://example.org/cotyledon-tomentosa",
        min_confidence=0.8,
        review_status=ReviewStatus.auto_ingested,
        covered_aspect="watering_frequency_or_trigger",
        evidence_type="validated_web_claim",
        source_provenance="trusted",
        answerability_status="full",
        retrieved_after=retrieved_at,
        created_before=created_at,
    )

    specs = build_metadata_filter_specs(filters)
    mapped = {(spec.key, spec.operator): spec.value for spec in specs}

    assert mapped[("species_id", None)] == "00000000-0000-0000-0000-000000000001"
    assert mapped[("scientific_name", None)] == "Cotyledon tomentosa"
    assert mapped[("topic", None)] == "watering"
    assert mapped[("source_domain", None)] == "example.org"
    assert mapped[("source_url", None)] == "https://example.org/cotyledon-tomentosa"
    assert mapped[("confidence", ">=")] == 0.8
    assert mapped[("review_status", None)] == "auto_ingested"
    assert mapped[("covered_aspects", "contains")] == "watering_frequency_or_trigger"
    assert mapped[("evidence_type", None)] == "validated_web_claim"
    assert mapped[("source_provenance", None)] == "trusted"
    assert mapped[("answerability_status", None)] == "full"
    assert mapped[("retrieved_at", ">=")] == retrieved_at.isoformat()
    assert mapped[("created_at", "<=")] == created_at.isoformat()


def test_knowledge_embedding_vector_column_uses_pgvector_type() -> None:
    vector_type = knowledge_embeddings.c.embedding_vector.type

    assert not isinstance(vector_type, sa.Text)
    assert vector_type.compile(dialect=postgresql.dialect()).lower() == "vector(1536)"


def test_knowledge_embedding_insert_binds_pgvector_type_for_postgresql() -> None:
    embedding = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
    statement = sa.insert(knowledge_embeddings).values(
        id=UUID("00000000-0000-0000-0000-000000000001"),
        chunk_id=UUID("00000000-0000-0000-0000-000000000002"),
        provider="test",
        model="test-embedding",
        embedding=embedding,
        embedding_vector=embedding,
        embedding_dimension=len(embedding),
    )

    compiled = statement.compile(dialect=postgresql.dialect())
    vector_bind = compiled.binds["embedding_vector"]

    assert not isinstance(vector_bind.type, sa.Text | sa.String)
    assert vector_bind.type.compile(dialect=postgresql.dialect()).lower() == "vector(1536)"


def test_llamaindex_metadata_filters_can_be_built_with_injected_classes() -> None:
    class FakeFilter:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

    class FakeFilters:
        def __init__(self, *, filters, condition) -> None:
            self.filters = filters
            self.condition = condition

    result = build_llamaindex_metadata_filters(
        KnowledgeRetrievalFilters(topic="watering"),
        metadata_filter_cls=FakeFilter,
        metadata_filters_cls=FakeFilters,
    )

    assert result.condition == "and"
    assert result.filters[0].kwargs == {"key": "topic", "value": "watering"}


@pytest.mark.parametrize(
    ("filter_name", "value", "metadata_key"),
    [
        ("source_provenance", "trusted", "source_provenance"),
        ("source_provenance", "external_fallback", "source_provenance"),
        ("answerability_status", "full", "answerability_status"),
        ("answerability_status", "partial", "answerability_status"),
    ],
)
def test_llamaindex_metadata_filters_preserve_closed_claim_filters(
    filter_name: str,
    value: str,
    metadata_key: str,
) -> None:
    filters = KnowledgeRetrievalFilters.model_validate(
        {
            "topic": "watering",
            "covered_aspect": "watering_frequency_or_trigger",
            filter_name: value,
        }
    )

    mapped = {(spec.key, spec.operator): spec.value for spec in build_metadata_filter_specs(filters)}

    assert mapped[("topic", None)] == "watering"
    assert mapped[("covered_aspects", "contains")] == "watering_frequency_or_trigger"
    assert mapped[(metadata_key, None)] == value


@pytest.mark.asyncio
async def test_llamaindex_retrieval_uses_app_configured_embed_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class FakeVectorStoreIndex:
        @classmethod
        def from_vector_store(cls, vector_store, **kwargs):
            captured.update(kwargs)
            return cls()

        def as_retriever(self, **kwargs):
            class FakeRetriever:
                def retrieve(self, bundle):
                    return []

            return FakeRetriever()

    class FakeFilter:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

    class FakeFilters:
        def __init__(self, *, filters, condition) -> None:
            self.filters = filters
            self.condition = condition

    async def _noop_initialize(self, store):
        pass

    monkeypatch.setattr(
        LlamaIndexRuntime, "_initialize_vector_store", _noop_initialize
    )
    monkeypatch.setattr(
        "app.knowledge.rag.runtime.create_llamaindex_pgvector_store", lambda settings: object()
    )
    monkeypatch.setattr(
        "app.knowledge.rag.runtime.create_llamaindex_embed_model",
        lambda settings: "app-owned-embed-model",
    )
    monkeypatch.setitem(
        __import__("sys").modules,
        "llama_index.core",
        type("FakeCore", (), {"VectorStoreIndex": FakeVectorStoreIndex})(),
    )
    monkeypatch.setitem(
        __import__("sys").modules,
        "llama_index.core.schema",
        type("FakeSchema", (), {"QueryBundle": lambda *args, **kwargs: (args, kwargs)})(),
    )
    monkeypatch.setitem(
        __import__("sys").modules,
        "llama_index.core.vector_stores",
        type(
            "FakeVectorStores",
            (),
            {"MetadataFilter": FakeFilter, "MetadataFilters": FakeFilters},
        )(),
    )

    nodes = await LlamaIndexRuntime().retrieve_nodes(
        filters=KnowledgeRetrievalFilters(topic="watering"),
        query_text="Cotyledon watering",
        query_embedding=[0.0],
        limit=5,
    )

    assert nodes == []
    assert captured["embed_model"] == "app-owned-embed-model"


@pytest.mark.asyncio
async def test_precomputed_embedding_adapter_fails_if_llamaindex_embeds_directly() -> None:
    class FakeBaseEmbedding:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

    embed_model = PrecomputedEmbeddingOnly.from_base_embedding(FakeBaseEmbedding, embed_dim=8)

    assert embed_model.kwargs["model_name"] == "precomputed-app-embedding-8d"
    with pytest.raises(RuntimeError, match="precomputed embeddings"):
        embed_model._get_query_embedding("query")
    with pytest.raises(RuntimeError, match="precomputed embeddings"):
        embed_model._get_text_embedding("text")
    with pytest.raises(RuntimeError, match="precomputed embeddings"):
        await embed_model._aget_query_embedding("query")


@pytest.mark.asyncio
async def test_app_embedding_transform_attaches_embeddings_to_pipeline_nodes() -> None:
    provider = RecordingEmbeddingProvider()
    adapter = AppEmbeddingTransform(provider)
    transform = adapter.as_llamaindex_transform(FakeTransformComponent, FakeMetadataMode)
    nodes = [
        FakeNode("first chunk", {"topic": "watering"}),
        FakeNode("second chunk", {"topic": "light"}),
    ]

    result = await transform.acall(nodes)

    assert result == nodes
    assert nodes[0].embedding == [1.0]
    assert nodes[1].embedding == [2.0]
    assert nodes[0].metadata == {"topic": "watering"}
    assert nodes[1].metadata == {"topic": "light"}
    assert adapter.result is not None
    assert adapter.result.provider == "recording"
    assert adapter.result.model == "recording-model"
    assert provider.calls == [
        (
            ["first chunk", "second chunk"],
            {"metadata": [{"topic": "watering"}, {"topic": "light"}]},
        )
    ]


@pytest.mark.asyncio
async def test_app_embedding_transform_ignores_empty_nodes() -> None:
    provider = RecordingEmbeddingProvider()
    adapter = AppEmbeddingTransform(provider)
    transform = adapter.as_llamaindex_transform(FakeTransformComponent, FakeMetadataMode)
    nodes = [FakeNode("   ", {"topic": "empty"})]

    result = await transform.acall(nodes)

    assert result == nodes
    assert nodes[0].embedding is None
    assert adapter.result is None
    assert provider.calls == []


def test_backend_declares_llamaindex_pgvector_dependencies() -> None:
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    content = pyproject.read_text(encoding="utf-8")

    assert "llama-index-core" in content
    assert "llama-index-vector-stores-postgres" in content


@pytest.mark.asyncio
async def test_page_evidence_fetcher_real_fetch_path_uses_configured_redirect_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.knowledge.safe_http import SafeFetchResult

    class FakeClient:
        def __init__(self) -> None:
            self.requests: list[str] = []

        def get(self, url: str) -> SafeFetchResult:
            self.requests.append(url)
            return SafeFetchResult(
                final_url=url,
                status=200,
                headers={
                    "Content-Type": "text/html; charset=utf-8",
                    "ETag": '"v1"',
                },
                body=b"<html><body>Fetched trusted watering guidance.</body></html>",
            )

    client = FakeClient()
    fetcher = TrustedPageEvidenceFetcher(
        TrustedSourceValidator(["example.org"]),
        http_client=client,  # type: ignore[arg-type]
    )

    evidence = await fetcher.fetch(_search_result())

    assert evidence.error is None
    assert evidence.content == "Fetched trusted watering guidance."
    assert evidence.has_fetched_content is True
    assert evidence.evidence_source == "fetched_content"
    assert evidence.fetch_status == "fetched"
    assert evidence.fetched_content_length == len("Fetched trusted watering guidance.")
    assert evidence.canonical_url == "https://example.org/watering"
    assert evidence.source_version == "etag:v1"
    assert client.requests == ["https://example.org/watering"]


@pytest.mark.asyncio
async def test_page_evidence_fetcher_rejects_non_https_before_fetch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fetcher = TrustedPageEvidenceFetcher(TrustedSourceValidator(["example.org"]))
    evidence = await fetcher.fetch(
        _search_result(url="http://example.org/watering", snippet="Trusted HTTP snippet.")
    )

    assert evidence.content is None
    assert evidence.evidence_text == "Trusted HTTP snippet."
    assert evidence.fetch_status == "skipped"
    assert evidence.fetch_error_category == "untrusted_source"


@pytest.mark.asyncio
async def test_page_evidence_fetcher_does_not_fetch_untrusted_url() -> None:
    class RecordingFetcher(TrustedPageEvidenceFetcher):
        def __init__(self) -> None:
            super().__init__(TrustedSourceValidator(["example.org"]))
            self.fetch_attempts = 0

        def _fetch_sync(self, result):
            self.fetch_attempts += 1
            return "Should not be fetched."

    fetcher = RecordingFetcher()
    evidence = await fetcher.fetch(
        _search_result(
            url="https://blog.invalid/watering",
            snippet="Untrusted snippet.",
            source_domain="blog.invalid",
        )
    )

    assert fetcher.fetch_attempts == 0
    assert evidence.content is None
    assert evidence.evidence_text == "Untrusted snippet."
    assert evidence.fetch_status == "skipped"


@pytest.mark.asyncio
async def test_page_evidence_fetcher_caps_trusted_fetches_to_three() -> None:
    class RecordingFetcher(TrustedPageEvidenceFetcher):
        def __init__(self) -> None:
            super().__init__(TrustedSourceValidator(["example.org"]))
            self.fetched_urls: list[str] = []

        async def fetch(self, result):
            self.fetched_urls.append(result.url)
            return TrustedPageEvidence(result=result, content=f"Fetched {result.url}")

    results = [
        _search_result(url=f"https://example.org/source-{index}")
        for index in range(4)
    ]
    fetcher = RecordingFetcher()

    evidence = await fetcher.fetch_all(results)

    assert fetcher.fetched_urls == [
        "https://example.org/source-0",
        "https://example.org/source-1",
        "https://example.org/source-2",
    ]
    assert [item.result.url for item in evidence] == fetcher.fetched_urls


@pytest.mark.asyncio
async def test_page_evidence_fetcher_returns_snippet_for_unsupported_content_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.knowledge.safe_http import SafeFetchResult

    class FakeClient:
        def get(self, url: str) -> SafeFetchResult:
            return SafeFetchResult(
                final_url=url,
                status=200,
                headers={"Content-Type": "application/json"},
                body=b'{"watering": "moderate"}',
            )

    fetcher = TrustedPageEvidenceFetcher(
        TrustedSourceValidator(["example.org"]),
        http_client=FakeClient(),  # type: ignore[arg-type]
    )

    evidence = await fetcher.fetch(_search_result(snippet="Trusted snippet fallback."))

    assert evidence.content is None
    assert evidence.error == "unsupported content type: application/json"
    assert evidence.evidence_text == "Trusted snippet fallback."
    assert evidence.fetch_status == "failed"
    assert evidence.fetch_error_category == "unsupported_content_type"


@pytest.mark.asyncio
async def test_page_evidence_fetcher_returns_snippet_for_oversized_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.knowledge.safe_http import SafeFetchResult

    class FakeClient:
        def get(self, url: str) -> SafeFetchResult:
            return SafeFetchResult(
                final_url=url,
                status=200,
                headers={"Content-Type": "text/plain"},
                body=b"x" * 6,
            )

    fetcher = TrustedPageEvidenceFetcher(
        TrustedSourceValidator(["example.org"]),
        max_response_bytes=5,
        http_client=FakeClient(),  # type: ignore[arg-type]
    )

    evidence = await fetcher.fetch(_search_result(snippet="Trusted snippet fallback."))

    assert evidence.content is None
    assert evidence.error == "response exceeded maximum size"
    assert evidence.evidence_text == "Trusted snippet fallback."
    assert evidence.fetch_error_category == "too_large"


@pytest.mark.asyncio
async def test_page_evidence_fetcher_returns_snippet_for_trust_crossing_redirect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.knowledge.safe_http import UnsafeDestinationError

    class FakeClient:
        def get(self, url: str) -> object:
            raise UnsafeDestinationError(detail="untrusted redirect hostname")

    fetcher = TrustedPageEvidenceFetcher(
        TrustedSourceValidator(["example.org"]),
        http_client=FakeClient(),  # type: ignore[arg-type]
    )

    evidence = await fetcher.fetch(_search_result(snippet="Trusted snippet fallback."))

    assert evidence.content is None
    assert evidence.evidence_text == "Trusted snippet fallback."
    assert evidence.fetch_status == "failed"
    assert evidence.fetch_error_category == "redirect"


def _document(topic: str = "care") -> KnowledgeDocumentInput:
    return KnowledgeDocumentInput(
        scientific_name="Cotyledon tomentosa",
        topic=topic,
        title="Cotyledon tomentosa care",
        content=(
            "Cotyledon tomentosa requires bright indirect light, restrained watering, "
            "and a fast draining mineral substrate. Avoid persistent moisture around roots."
        ),
        confidence=0.85,
        review_status=ReviewStatus.auto_ingested,
        sources=[
            KnowledgeSourceInput(
                title="Trusted botanical source",
                url="https://example.org/cotyledon-tomentosa",
                source_domain="example.org",
                retrieved_at=datetime.now(UTC),
            )
        ],
    )


def _search_result(
    *,
    url: str = "https://example.org/watering",
    snippet: str = "Trusted search snippet.",
    source_domain: str = "example.org",
) -> SearchResult:
    return SearchResult(
        title="Trusted watering guide",
        url=url,
        snippet=snippet,
        source_domain=source_domain,
    )


def test_balance_enrichment_chunks_round_robins_and_deduplicates() -> None:
    from app.knowledge.acquisition import balance_enrichment_chunks

    def _chunk(chunk_id: str) -> object:
        return SimpleNamespace(id=chunk_id, content=chunk_id)

    hits = {
        "aspect_a": [_chunk("a1"), _chunk("a2"), _chunk("a3")],
        "aspect_b": [_chunk("b1"), _chunk("b2")],
        "aspect_c": [_chunk("c1")],
    }
    balanced = balance_enrichment_chunks(hits, budget=20)
    assert [chunk.id for chunk in balanced] == [
        "a1",
        "b1",
        "c1",
        "a2",
        "b2",
        "a3",
    ]

    capped = balance_enrichment_chunks(hits, budget=4)
    assert [chunk.id for chunk in capped] == ["a1", "b1", "c1", "a2"]

    with_duplicates = {
        "aspect_a": [_chunk("dup"), _chunk("x1")],
        "aspect_b": [_chunk("dup"), _chunk("y1")],
    }
    deduped = balance_enrichment_chunks(with_duplicates, budget=20)
    assert [chunk.id for chunk in deduped] == ["dup", "x1", "y1"]


async def test_retrieve_balanced_enrichment_gives_every_aspect_a_first_candidate(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """With 17 requested aspects and a budget of 20, every available aspect
    contributes one candidate before any aspect contributes a duplicate."""
    from app.enrichment.identity import CanonicalSpeciesIdentity
    from app.knowledge.acquisition import retrieve_balanced_enrichment

    aspects = [
        "watering_frequency_or_trigger",
        "light_exposure",
        "soil_drainage",
        "climate_temperature_range",
        "humidity_preference",
        "watering_amount",
        "nutrition_feeding_schedule",
        "nutrition_fertilizer_type",
        "pest_identification",
        "pest_prevention_steps",
        "disease_identification",
        "disease_prevention_steps",
        "toxicity_pet_safety",
        "toxicity_human_edibility",
        "toxicity_child_safety",
        "toxicity_handling_precautions",
        "general_care_summary",
    ]
    assert len(aspects) == 17

    class ManyAspectRuntime(FakeLlamaRuntime):
        def __init__(self) -> None:
            super().__init__()
            self.aspect_order: list[str] = []

        async def retrieve_nodes(self, *, filters, query_text, query_embedding, limit):
            self.retrieve_calls += 1
            self.aspect_order.append(filters.covered_aspect)
            chunk_id = by_aspect[filters.covered_aspect]
            return [FakeRetrievedNode(chunk_id, 0.9)]

    async with session_factory() as session:
        repository = KnowledgeRepository(session)
        by_aspect: dict[str, UUID] = {}
        for index, aspect in enumerate(aspects):
            _, chunk_id = await _persist_enrichment_chunk(
                session, aspect=aspect, content=f"Evidence content for {aspect}."
            )
            by_aspect[aspect] = chunk_id
        await session.commit()
        runtime = ManyAspectRuntime()
        identity = CanonicalSpeciesIdentity(
            accepted_gbif_key=1,
            normalized_binomial="Cotyledon tomentosa",
            taxonomy_validated=True,
        )
        result = await retrieve_balanced_enrichment(
            vector_index=KnowledgeVectorIndex(repository, runtime=runtime),
            canonical_species_key=identity.key,
            accepted_gbif_key=1,
            required_aspects=aspects,
            query_text="care",
            query_embedding=[0.1] * 8,
            per_aspect_limit=5,
            budget=20,
        )
    assert runtime.retrieve_calls == 17
    assert runtime.aspect_order == aspects
    assert len(result) == 17
    ids = [str(chunk.id) for chunk in result]
    assert len(set(ids)) == 17
    for aspect in aspects:
        assert str(by_aspect[aspect]) in ids


async def test_retrieve_balanced_enrichment_deduplicates_shared_chunks(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    from app.enrichment.identity import CanonicalSpeciesIdentity
    from app.knowledge.acquisition import retrieve_balanced_enrichment

    shared_aspect = "light_exposure"
    other_aspect = "soil_drainage"

    class SharedRuntime(FakeLlamaRuntime):
        def __init__(self) -> None:
            super().__init__()
            self.queries: list[str] = []

        async def retrieve_nodes(self, *, filters, query_text, query_embedding, limit):
            self.retrieve_calls += 1
            self.queries.append(filters.covered_aspect)
            return [FakeRetrievedNode(shared_chunk_id, 0.5)]

    async with session_factory() as session:
        repository = KnowledgeRepository(session)
        _, shared_chunk_id = await _persist_enrichment_chunk(
            session, aspect=shared_aspect, content="Shared evidence content."
        )
        await session.commit()
        runtime = SharedRuntime()
        identity = CanonicalSpeciesIdentity(
            accepted_gbif_key=1,
            normalized_binomial="Cotyledon tomentosa",
            taxonomy_validated=True,
        )
        result = await retrieve_balanced_enrichment(
            vector_index=KnowledgeVectorIndex(repository, runtime=runtime),
            canonical_species_key=identity.key,
            accepted_gbif_key=1,
            required_aspects=[shared_aspect, other_aspect],
            query_text="care",
            query_embedding=[0.1] * 8,
            per_aspect_limit=5,
            budget=20,
        )
    assert [str(chunk.id) for chunk in result] == [str(shared_chunk_id)]
    assert runtime.retrieve_calls == 2


async def test_per_aspect_retrieval_requires_validation_provenance_for_that_aspect(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """A chunk covering aspects A and B is eligible for aspect A only when its
    validation provenance covers A. Provenance that only covers the sibling
    aspect B cannot make the chunk a candidate for an A query, so an A-only
    validated chunk must not be injected into the balanced A slot."""
    import hashlib

    from app.enrichment.evidence import stable_enrichment_document_id
    from app.enrichment.identity import CanonicalSpeciesIdentity
    from app.knowledge.acquisition import retrieve_balanced_enrichment
    from app.knowledge.schemas import EnrichmentEvidenceMetadata

    aspect_a = "light_exposure"
    aspect_b = "soil_drainage"
    identity = CanonicalSpeciesIdentity(
        accepted_gbif_key=1,
        normalized_binomial="Cotyledon tomentosa",
        taxonomy_validated=True,
    )
    now = datetime.now(UTC)
    taxonomy_id = uuid4()

    async def _persist(*, covered: list[str], validated: list[str]) -> UUID:
        job_id = uuid4()
        doc_id = stable_enrichment_document_id(f"fixture-{uuid4()}-content-key")
        chunk_id = uuid4()
        validation_run_id = uuid4()
        async with session_factory() as session:
            repository = KnowledgeRepository(session)
            metadata = EnrichmentEvidenceMetadata(
                canonical_species_key=identity.key,
                accepted_gbif_key=identity.accepted_gbif_key,
                normalized_binomial=identity.normalized_binomial,
                canonical_source_url="https://example.org/care",
                canonical_source_domain="example.org",
                source_version="etag-v1",
                normalized_content_hash=hashlib.sha256("-".join(covered).encode()).hexdigest(),
                source_retrieved_at=now,
                enrichment_provenance={"kind": "confirmed_plant_enrichment", "version": 1},
                taxonomy_provenance_id=taxonomy_id,
            )
            document = KnowledgeDocumentInput(
                scientific_name=identity.normalized_binomial,
                topic="confirmed_plant_enrichment",
                title="Shared aspect evidence",
                content="Shared evidence content covering both aspects.",
                confidence=0.9,
                review_status=ReviewStatus.auto_ingested,
                sources=[
                    KnowledgeSourceInput(
                        title="Care evidence",
                        url="https://example.org/care",
                        source_domain="example.org",
                        retrieved_at=now,
                        validation_status="trusted",
                    )
                ],
                metadata={
                    "covered_aspects": covered,
                    "evidence_type": "confirmed_plant_enrichment",
                    "source_provenance": "trusted",
                    "canonical_species_key": identity.key,
                },
            )
            chunk = KnowledgeChunk(
                id=chunk_id,
                document_id=doc_id,
                chunk_index=0,
                content="Shared evidence content covering both aspects.",
                metadata=document.metadata,
                scientific_name=identity.normalized_binomial,
                topic=document.topic,
                source_domain="example.org",
                source_url="https://example.org/care",
                confidence=0.9,
                review_status=ReviewStatus.auto_ingested,
                retrieved_at=now,
            )
            await repository.save_document(
                document,
                chunks=[chunk],
                commit=False,
                document_id=doc_id,
                enrichment=metadata,
            )
            await repository.add_enrichment_aspect_supports(
                document_id=doc_id,
                aspects=covered,
                confidence=0.9,
                review_status=ReviewStatus.auto_ingested,
            )
            await repository.add_enrichment_validation_run(
                validation_id=validation_run_id,
                job_id=job_id,
                taxonomy_provenance_id=taxonomy_id,
                policy_version=1,
                required_aspects=covered,
                covered_aspects=validated,
                missing_aspects=[a for a in covered if a not in validated],
                answerability_status="partial",
                judge_confidence=0.9,
                validation_metadata={"acquisition_avoided": False},
            )
            await repository.add_enrichment_validation_evidence(
                validation_id=validation_run_id,
                document_id=doc_id,
            )
            await session.commit()
        return chunk_id

    # chunk_ab supports A and B but its validation provenance covers only B.
    chunk_ab = await _persist(covered=[aspect_a, aspect_b], validated=[aspect_b])
    # chunk_b supports and validates only B, a legitimate B candidate.
    chunk_b = await _persist(covered=[aspect_b], validated=[aspect_b])

    class AspectProvenanceRuntime(FakeLlamaRuntime):
        def __init__(self) -> None:
            super().__init__()
            self.aspect_order: list[str] = []

        async def retrieve_nodes(self, *, filters, query_text, query_embedding, limit):
            self.retrieve_calls += 1
            self.aspect_order.append(filters.covered_aspect)
            if filters.covered_aspect == aspect_a:
                return [FakeRetrievedNode(chunk_ab, 0.9)]
            return [FakeRetrievedNode(chunk_b, 0.9), FakeRetrievedNode(chunk_ab, 0.85)]

    async with session_factory() as session:
        repository = KnowledgeRepository(session)
        runtime = AspectProvenanceRuntime()
        result = await retrieve_balanced_enrichment(
            vector_index=KnowledgeVectorIndex(repository, runtime=runtime),
            canonical_species_key=identity.key,
            accepted_gbif_key=1,
            required_aspects=[aspect_a, aspect_b],
            query_text="care",
            query_embedding=[0.1] * 8,
            per_aspect_limit=5,
            budget=20,
        )

    # chunk_ab is NOT a valid aspect A candidate (no A provenance), so the
    # balanced order must start with the legitimate B chunk; injecting
    # chunk_ab into the A slot first would reorder these two chunks.
    assert runtime.aspect_order == [aspect_a, aspect_b]
    assert [str(chunk.id) for chunk in result] == [str(chunk_b), str(chunk_ab)]


def test_source_version_prefers_etag_over_last_modified_and_hash() -> None:
    from app.knowledge.page_evidence import _source_version_from_headers

    assert (
        _source_version_from_headers({"ETag": '"v1"', "Last-Modified": "Wed, 01 Aug 2026 00:00:00 GMT"}, "content")
        == "etag:v1"
    )
    assert (
        _source_version_from_headers({"ETag": "W/weak"}, "content")
        == "etag:W/weak"
    )
    assert (
        _source_version_from_headers(
            {"Last-Modified": "Wed, 01 Aug 2026 00:00:00 GMT"}, "content"
        )
        == "last-modified:Wed, 01 Aug 2026 00:00:00 GMT"
    )


def test_source_version_normalizes_header_name_case() -> None:
    from app.knowledge.page_evidence import _source_version_from_headers

    assert (
        _source_version_from_headers({"etag": '"v1"'}, "content")
        == _source_version_from_headers({"ETag": '"v1"'}, "content")
    )
    assert (
        _source_version_from_headers({"eTaG": '"v1"'}, "content")
        == _source_version_from_headers({"ETag": '"v1"'}, "content")
    )
    assert (
        _source_version_from_headers(
            {"last-modified": "Wed, 01 Aug 2026 00:00:00 GMT"}, "content"
        )
        == _source_version_from_headers(
            {"Last-Modified": "Wed, 01 Aug 2026 00:00:00 GMT"}, "content"
        )
    )


def test_source_version_uses_lowercase_last_modified_when_etag_absent() -> None:
    from app.knowledge.page_evidence import _source_version_from_headers

    assert (
        _source_version_from_headers(
            {"last-modified": "Wed, 01 Aug 2026 00:00:00 GMT"}, "content"
        )
        == "last-modified:Wed, 01 Aug 2026 00:00:00 GMT"
    )


@pytest.mark.asyncio
async def test_page_evidence_accepts_lowercase_content_type_header() -> None:
    from app.knowledge.safe_http import SafeFetchResult

    class FakeClient:
        def get(self, url: str) -> SafeFetchResult:
            return SafeFetchResult(
                final_url=url,
                status=200,
                headers={"content-type": "text/plain; charset=utf-8"},
                body=b"lowercase header fetch ok",
            )

    fetcher = TrustedPageEvidenceFetcher(
        TrustedSourceValidator(["example.org"]),
        http_client=FakeClient(),  # type: ignore[arg-type]
    )

    evidence = await fetcher.fetch(_search_result(snippet="snippet"))

    assert evidence.fetch_status == "fetched"
    assert evidence.response_content_type == "text/plain"
    assert evidence.content == "lowercase header fetch ok"


def test_source_version_falls_back_to_content_hash() -> None:
    import hashlib

    from app.knowledge.page_evidence import _source_version_from_headers

    content = "  normalized   content  "
    version = _source_version_from_headers({}, content)
    normalized = "normalized content"
    expected = f"sha256:{hashlib.sha256(normalized.encode()).hexdigest()}"
    assert version == expected


def test_publication_date_is_null_when_unreliable() -> None:
    from datetime import UTC, datetime

    from app.knowledge.page_evidence import TrustedPageEvidence
    from app.providers.types import SearchResult

    page = TrustedPageEvidence(
        result=SearchResult(
            title="t",
            url="https://example.org/care",
            snippet="s",
            source_domain="example.org",
        ),
        content="Fetched content.",
        fetch_status="fetched",
        canonical_url="https://example.org/care",
        retrieved_at=datetime.now(UTC),
        source_version="etag:v1",
    )
    assert page.published_at is None
