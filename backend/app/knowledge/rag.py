from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Sequence
from urllib.parse import quote
from uuid import UUID

from sqlalchemy.engine import make_url

from app.core.settings import Settings, get_settings
from app.knowledge.chunking import build_chunk_metadata
from app.knowledge.repository import KnowledgeRepository
from app.knowledge.schemas import KnowledgeChunk, KnowledgeDocumentInput, KnowledgeRetrievalFilters
from app.providers.interfaces import EmbeddingProvider
from app.providers.types import EmbeddingResult


@dataclass(frozen=True)
class LlamaIndexPgVectorConfig:
    database: str
    host: str
    password: str | None
    port: int
    user: str | None
    table_name: str
    embed_dim: int


@dataclass(frozen=True)
class MetadataFilterSpec:
    key: str
    value: object
    operator: str | None = None


@dataclass(frozen=True)
class RetrievedNode:
    chunk_id: UUID
    score: float | None = None


@dataclass(frozen=True)
class OrchestratedKnowledgeIngestion:
    chunks: list[KnowledgeChunk]
    embeddings: list[list[float]]
    provider: str
    model: str | None


class AppEmbeddingTransform:
    def __init__(self, embedding_provider: EmbeddingProvider) -> None:
        self.embedding_provider = embedding_provider
        self.result: EmbeddingResult | None = None

    def as_llamaindex_transform(self, transform_component_cls, metadata_mode_cls):
        parent = self

        class _Transform(transform_component_cls):
            async def acall(self, nodes: Sequence[Any], **kwargs: Any) -> Sequence[Any]:
                embeddable_nodes = []
                texts = []
                metadata = []
                for node in nodes:
                    text = node.get_content(metadata_mode=metadata_mode_cls.NONE).strip()
                    if not text:
                        continue
                    embeddable_nodes.append(node)
                    texts.append(text)
                    metadata.append(dict(getattr(node, "metadata", {}) or {}))

                if not texts:
                    parent.result = None
                    return nodes

                result = await parent.embedding_provider.create_embeddings(texts, metadata=metadata)
                if len(result.embeddings) != len(embeddable_nodes):
                    raise ValueError("Embedding count must match LlamaIndex node count")

                for node, embedding in zip(embeddable_nodes, result.embeddings, strict=True):
                    node.embedding = embedding

                parent.result = result
                return nodes

            def __call__(self, nodes: Sequence[Any], **kwargs: Any) -> Sequence[Any]:
                raise RuntimeError("AppEmbeddingTransform requires async LlamaIndex ingestion")

        return _Transform()


def get_pgvector_config(settings: Settings | None = None) -> LlamaIndexPgVectorConfig:
    settings = settings or get_settings()
    url = make_url(settings.database_url)
    return LlamaIndexPgVectorConfig(
        database=url.database or "fotosintesis",
        host=url.host or "localhost",
        password=url.password,
        port=url.port or 5432,
        user=url.username,
        table_name=settings.knowledge_vector_table,
        embed_dim=settings.embedding_dimension,
    )


def build_metadata_filter_specs(filters: KnowledgeRetrievalFilters) -> list[MetadataFilterSpec]:
    filter_specs: list[MetadataFilterSpec] = []
    for key in ("species_id", "scientific_name", "topic", "source_domain", "source_url"):
        value = getattr(filters, key)
        if value is not None:
            filter_specs.append(MetadataFilterSpec(key=key, value=str(value)))
    if filters.min_confidence is not None:
        filter_specs.append(
            MetadataFilterSpec(key="confidence", value=filters.min_confidence, operator=">=")
        )
    if filters.review_status is not None:
        filter_specs.append(
            MetadataFilterSpec(key="review_status", value=filters.review_status.value)
        )
    if filters.retrieved_after is not None:
        filter_specs.append(
            MetadataFilterSpec(
                key="retrieved_at",
                value=filters.retrieved_after.isoformat(),
                operator=">=",
            )
        )
    if filters.retrieved_before is not None:
        filter_specs.append(
            MetadataFilterSpec(
                key="retrieved_at",
                value=filters.retrieved_before.isoformat(),
                operator="<=",
            )
        )
    if filters.created_after is not None:
        filter_specs.append(
            MetadataFilterSpec(
                key="created_at",
                value=filters.created_after.isoformat(),
                operator=">=",
            )
        )
    if filters.created_before is not None:
        filter_specs.append(
            MetadataFilterSpec(
                key="created_at",
                value=filters.created_before.isoformat(),
                operator="<=",
            )
        )
    return filter_specs


def build_llamaindex_metadata_filters(
    filters: KnowledgeRetrievalFilters,
    *,
    metadata_filter_cls=None,
    metadata_filters_cls=None,
):
    if metadata_filter_cls is None or metadata_filters_cls is None:
        try:
            from llama_index.core.vector_stores import MetadataFilter, MetadataFilters
        except ImportError as exc:
            raise RuntimeError(
                "Install llama-index-core to build LlamaIndex metadata filters"
            ) from exc
        metadata_filter_cls = MetadataFilter
        metadata_filters_cls = MetadataFilters

    llama_filters = []
    for spec in build_metadata_filter_specs(filters):
        kwargs = {"key": spec.key, "value": spec.value}
        if spec.operator is not None:
            kwargs["operator"] = spec.operator
        llama_filters.append(metadata_filter_cls(**kwargs))
    return metadata_filters_cls(filters=llama_filters, condition="and")


def create_llamaindex_pgvector_store(settings: Settings | None = None):
    try:
        from llama_index.vector_stores.postgres import PGVectorStore
    except ImportError as exc:
        raise RuntimeError(
            "Install llama-index-vector-stores-postgres to use PGVectorStore"
        ) from exc

    config = get_pgvector_config(settings)
    return PGVectorStore.from_params(
        database=config.database,
        host=config.host,
        password=config.password,
        port=config.port,
        user=config.user,
        table_name=config.table_name,
        embed_dim=config.embed_dim,
    )


def create_llamaindex_embed_model(settings: Settings | None = None):
    try:
        from llama_index.core.embeddings import BaseEmbedding
    except ImportError as exc:
        raise RuntimeError("Install llama-index-core to configure LlamaIndex embeddings") from exc

    settings = settings or get_settings()
    return PrecomputedEmbeddingOnly.from_base_embedding(BaseEmbedding, settings.embedding_dimension)


class PrecomputedEmbeddingOnly:
    error_message = (
        "LlamaIndex must receive precomputed embeddings from the app EmbeddingProvider; "
        "direct LlamaIndex embedding generation is disabled."
    )

    @staticmethod
    def from_base_embedding(base_embedding_cls, embed_dim: int):
        class _PrecomputedEmbeddingOnly(base_embedding_cls):
            def __init__(self) -> None:
                super().__init__(
                    model_name=f"precomputed-app-embedding-{embed_dim}d", embed_batch_size=1
                )

            def _get_query_embedding(self, query: str) -> list[float]:
                raise RuntimeError(PrecomputedEmbeddingOnly.error_message)

            async def _aget_query_embedding(self, query: str) -> list[float]:
                raise RuntimeError(PrecomputedEmbeddingOnly.error_message)

            def _get_text_embedding(self, text: str) -> list[float]:
                raise RuntimeError(PrecomputedEmbeddingOnly.error_message)

            async def _aget_text_embedding(self, text: str) -> list[float]:
                raise RuntimeError(PrecomputedEmbeddingOnly.error_message)

            def _get_text_embeddings(self, texts: list[str]) -> list[list[float]]:
                raise RuntimeError(PrecomputedEmbeddingOnly.error_message)

        return _PrecomputedEmbeddingOnly()


class LlamaIndexRuntime:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings

    async def orchestrate_ingestion(
        self,
        *,
        document: KnowledgeDocumentInput,
        embedding_provider: EmbeddingProvider,
    ) -> OrchestratedKnowledgeIngestion:
        try:
            from llama_index.core import Document
            from llama_index.core.ingestion import IngestionPipeline
            from llama_index.core.node_parser import SentenceSplitter
            from llama_index.core.schema import MetadataMode, TransformComponent
        except ImportError as exc:
            raise RuntimeError("Install llama-index-core to ingest knowledge documents") from exc

        if not document.sources:
            raise ValueError("Knowledge documents require at least one trusted source")

        source = document.sources[0]
        created_at = datetime.now(timezone.utc)
        base_metadata = build_chunk_metadata(
            species_id=document.species_id,
            scientific_name=document.scientific_name,
            topic=document.topic,
            source_domain=source.source_domain,
            source_url=str(source.url),
            confidence=document.confidence,
            review_status=document.review_status.value,
            retrieved_at=source.retrieved_at,
            created_at=created_at,
        )
        embedding_transform = AppEmbeddingTransform(embedding_provider)
        pipeline = IngestionPipeline(
            transformations=[
                SentenceSplitter(chunk_size=900, chunk_overlap=120),
                embedding_transform.as_llamaindex_transform(TransformComponent, MetadataMode),
            ]
        )
        nodes = await pipeline.arun(
            documents=[Document(text=document.content, metadata=base_metadata)]
        )
        chunks: list[KnowledgeChunk] = []
        embeddings: list[list[float]] = []
        for index, node in enumerate(nodes):
            content = node.get_content(metadata_mode=MetadataMode.NONE).strip()
            if not content:
                continue
            if node.embedding is None:
                raise ValueError("LlamaIndex ingestion produced a chunk without an embedding")
            chunks.append(
                KnowledgeChunk(
                    chunk_index=index,
                    content=content,
                    metadata=dict(base_metadata),
                    species_id=document.species_id,
                    scientific_name=document.scientific_name,
                    topic=document.topic,
                    source_domain=source.source_domain,
                    source_url=str(source.url),
                    confidence=document.confidence,
                    review_status=document.review_status,
                    retrieved_at=source.retrieved_at,
                    created_at=created_at,
                )
            )
            embeddings.append(node.embedding)
        if not chunks:
            raise ValueError("LlamaIndex ingestion produced no knowledge chunks")
        if embedding_transform.result is None:
            raise ValueError("LlamaIndex ingestion produced no embeddings")

        return OrchestratedKnowledgeIngestion(
            chunks=chunks,
            embeddings=embeddings,
            provider=embedding_transform.result.provider,
            model=embedding_transform.result.model,
        )

    def index_chunks(
        self,
        *,
        chunks: list[KnowledgeChunk],
        embeddings: list[list[float]],
        provider: str,
        model: str | None,
    ) -> None:
        try:
            from llama_index.core import VectorStoreIndex
            from llama_index.core.schema import TextNode
        except ImportError as exc:
            raise RuntimeError("Install llama-index-core to index knowledge chunks") from exc

        if len(chunks) != len(embeddings):
            raise ValueError("Embedding count must match chunk count")

        nodes = []
        for chunk, embedding in zip(chunks, embeddings, strict=True):
            if chunk.id is None:
                raise ValueError("Cannot index an unsaved chunk")
            metadata = _llamaindex_chunk_metadata(chunk, provider=provider, model=model)
            node = TextNode(text=chunk.content, id_=str(chunk.id), metadata=metadata)
            node.embedding = embedding
            nodes.append(node)

        index = VectorStoreIndex.from_vector_store(
            vector_store=create_llamaindex_pgvector_store(self.settings),
            embed_model=create_llamaindex_embed_model(self.settings),
        )
        index.insert_nodes(nodes)

    def retrieve_nodes(
        self,
        *,
        filters: KnowledgeRetrievalFilters,
        query_text: str,
        query_embedding: list[float],
        limit: int,
    ) -> list[RetrievedNode]:
        try:
            from llama_index.core import VectorStoreIndex
            from llama_index.core.schema import QueryBundle
        except ImportError as exc:
            raise RuntimeError("Install llama-index-core to retrieve knowledge chunks") from exc

        index = VectorStoreIndex.from_vector_store(
            vector_store=create_llamaindex_pgvector_store(self.settings),
            embed_model=create_llamaindex_embed_model(self.settings),
        )
        retriever = index.as_retriever(
            similarity_top_k=limit,
            filters=build_llamaindex_metadata_filters(filters),
        )
        bundle = QueryBundle(query_str=query_text, embedding=query_embedding)
        return [_retrieved_node_from_score_node(node) for node in retriever.retrieve(bundle)]


class KnowledgeVectorIndex:
    def __init__(
        self,
        repository: KnowledgeRepository,
        *,
        runtime: LlamaIndexRuntime | None = None,
    ) -> None:
        self.repository = repository
        self.runtime = runtime or LlamaIndexRuntime()

    async def ingest_document(
        self,
        document: KnowledgeDocumentInput,
        *,
        embedding_provider: EmbeddingProvider,
    ):
        ingestion = await self.runtime.orchestrate_ingestion(
            document=document,
            embedding_provider=embedding_provider,
        )
        persisted = await self.repository.save_document(document, chunks=ingestion.chunks)
        await self.repository.add_embeddings(
            chunks=persisted.chunks,
            embeddings=ingestion.embeddings,
            provider=ingestion.provider,
            model=ingestion.model,
        )
        await self.index_chunks(
            chunks=persisted.chunks,
            embeddings=ingestion.embeddings,
            provider=ingestion.provider,
            model=ingestion.model,
        )
        return persisted

    async def index_chunks(
        self,
        *,
        chunks: list[KnowledgeChunk],
        embeddings: list[list[float]],
        provider: str,
        model: str | None,
    ) -> None:
        self.runtime.index_chunks(
            chunks=chunks,
            embeddings=embeddings,
            provider=provider,
            model=model,
        )

    async def retrieve_chunks(
        self,
        filters: KnowledgeRetrievalFilters,
        *,
        query_text: str,
        query_embedding: list[float],
        limit: int = 5,
    ) -> list[KnowledgeChunk]:
        nodes = self.runtime.retrieve_nodes(
            filters=filters,
            query_text=query_text,
            query_embedding=query_embedding,
            limit=limit,
        )
        chunk_map = await self.repository.get_chunks_by_ids([node.chunk_id for node in nodes])
        chunks: list[KnowledgeChunk] = []
        for node in nodes:
            chunk = chunk_map.get(node.chunk_id)
            if chunk is not None:
                chunks.append(chunk.model_copy(update={"score": node.score}))
        return chunks


def trusted_manual_search_url(scientific_name: str, topic: str) -> str:
    query = f"{scientific_name} {topic} site:gbif.org OR site:powo.science.kew.org"
    return f"https://www.google.com/search?q={quote(query)}"


def _llamaindex_chunk_metadata(
    chunk: KnowledgeChunk, *, provider: str, model: str | None
) -> dict[str, object]:
    metadata = dict(chunk.metadata)
    metadata.update(
        {
            "chunk_id": str(chunk.id),
            "document_id": str(chunk.document_id) if chunk.document_id else None,
            "source_id": str(chunk.source_id) if chunk.source_id else None,
            "embedding_provider": provider,
            "embedding_model": model,
        }
    )
    return metadata


def _retrieved_node_from_score_node(node) -> RetrievedNode:
    raw_node = getattr(node, "node", node)
    metadata = getattr(raw_node, "metadata", {}) or {}
    raw_id = (
        metadata.get("chunk_id")
        or getattr(raw_node, "node_id", None)
        or getattr(raw_node, "id_", None)
    )
    if raw_id is None:
        raise ValueError("LlamaIndex node is missing chunk_id metadata")
    return RetrievedNode(chunk_id=UUID(str(raw_id)), score=getattr(node, "score", None))
