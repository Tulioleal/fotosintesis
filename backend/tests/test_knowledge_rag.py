from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.tables import (
    knowledge_chunks,
    knowledge_documents,
    knowledge_embeddings,
    knowledge_sources,
)
from app.knowledge.acquisition import KnowledgeAcquisitionService, TrustedSourceValidator
from app.knowledge.rag import (
    AppEmbeddingTransform,
    KnowledgeVectorIndex,
    OrchestratedKnowledgeIngestion,
    build_llamaindex_metadata_filters,
    build_metadata_filter_specs,
)
from app.knowledge.repository import KnowledgeRepository
from app.knowledge.schemas import (
    AcquisitionStatus,
    KnowledgeChunk,
    KnowledgeDocumentInput,
    KnowledgeRetrievalFilters,
    KnowledgeSourceInput,
    ReviewStatus,
)
from app.providers.types import EmbeddingResult


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

    def index_chunks(self, *, chunks, embeddings, provider, model) -> None:
        self.index_calls += 1
        self.indexed_chunks = list(chunks)

    def retrieve_nodes(self, *, filters, query_text, query_embedding, limit):
        self.retrieve_calls += 1
        return [FakeRetrievedNode(chunk.id, 1.0) for chunk in self.indexed_chunks[:limit]]


class FailingLlamaRuntime(FakeLlamaRuntime):
    def retrieve_nodes(self, *, filters, query_text, query_embedding, limit):
        raise RuntimeError("pgvector unavailable")


class FailingIngestionRuntime(FakeLlamaRuntime):
    async def orchestrate_ingestion(self, *, document, embedding_provider):
        raise RuntimeError("LlamaIndex ingestion unavailable")


class FakeRetrievedNode:
    def __init__(self, chunk_id: UUID, score: float) -> None:
        self.chunk_id = chunk_id
        self.score = score


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
async def test_acquisition_uses_trusted_sources_embeds_and_retrieves(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        repository = KnowledgeRepository(session)
        runtime = FakeLlamaRuntime()
        service = KnowledgeAcquisitionService(
            repository,
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
async def test_acquisition_degrades_when_no_trusted_source_is_available(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        repository = KnowledgeRepository(session)
        service = KnowledgeAcquisitionService(
            repository,
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
        repository = KnowledgeRepository(session)
        service = KnowledgeAcquisitionService(
            repository,
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


@pytest.mark.asyncio
async def test_acquisition_does_not_use_sql_only_retrieval_path(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        repository = NoSqlVectorRepository(session)
        runtime = FakeLlamaRuntime()
        service = KnowledgeAcquisitionService(
            repository,
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
    retrieved_at = datetime(2026, 5, 1, tzinfo=timezone.utc)
    created_at = datetime(2026, 5, 2, tzinfo=timezone.utc)
    filters = KnowledgeRetrievalFilters(
        species_id=UUID("00000000-0000-0000-0000-000000000001"),
        scientific_name="Cotyledon tomentosa",
        topic="watering",
        source_domain="example.org",
        source_url="https://example.org/cotyledon-tomentosa",
        min_confidence=0.8,
        review_status=ReviewStatus.auto_ingested,
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
    assert mapped[("retrieved_at", ">=")] == retrieved_at.isoformat()
    assert mapped[("created_at", "<=")] == created_at.isoformat()


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
                retrieved_at=datetime.now(timezone.utc),
            )
        ],
    )
