"""LlamaIndex runtime wiring: pgvector store and metadata filters."""

from __future__ import annotations

import asyncio
import hashlib
import re
from datetime import datetime, timezone
from collections.abc import Callable
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.settings import Settings, get_settings
from app.knowledge.chunking import build_chunk_metadata
from app.knowledge.rag.embedding import AppEmbeddingTransform, PrecomputedEmbeddingOnly
from app.knowledge.rag.types import (
    LlamaIndexPgVectorConfig,
    MetadataFilterSpec,
    OrchestratedKnowledgeIngestion,
    RetrievedNode,
    VectorIndexError,
    VectorIndexIncomplete,
)
from app.knowledge.schemas import (
    KnowledgeChunk,
    KnowledgeDocumentInput,
    KnowledgeRetrievalFilters,
    ReviewStatus,
)
from app.providers.interfaces import EmbeddingProvider


def build_pgvector_config(settings: Settings) -> LlamaIndexPgVectorConfig:
    url = make_url(settings.database_url)
    database = url.database or ""
    return LlamaIndexPgVectorConfig(
        database=database,
        host=url.host or "localhost",
        password=url.password,
        port=url.port or 5432,
        user=url.username,
        table_name=settings.knowledge_vector_table,
        embed_dim=settings.embedding_dimension,
    )


def create_llamaindex_pgvector_store(settings: Settings) -> Any:
    config = build_pgvector_config(settings)
    try:
        from llama_index.vector_stores.postgres import PGVectorStore
    except ImportError as exc:
        raise RuntimeError(
            "Install llama-index-vector-stores-postgres to use the pgvector store"
        ) from exc
    return PGVectorStore.from_params(
        database=config.database,
        host=config.host,
        password=config.password,
        port=config.port,
        user=config.user,
        table_name=config.table_name,
        embed_dim=config.embed_dim,
        initialization_fail_on_error=True,
    )


def create_llamaindex_embed_model(settings: Settings) -> Any:
    try:
        from llama_index.core.embeddings import BaseEmbedding
    except ImportError as exc:
        raise RuntimeError(
            "Install llama-index-core to configure LlamaIndex embeddings"
        ) from exc
    return PrecomputedEmbeddingOnly.from_base_embedding(
        BaseEmbedding, settings.embedding_dimension
    )


def _llamaindex_chunk_metadata(
    chunk: KnowledgeChunk,
    *,
    provider: str,
    model: str | None,
    embedding_dimension: int,
) -> dict[str, Any]:
    metadata = build_chunk_metadata(
        species_id=chunk.species_id,
        scientific_name=chunk.scientific_name,
        topic=chunk.topic,
        source_domain=chunk.source_domain,
        source_url=chunk.source_url,
        confidence=chunk.confidence,
        review_status=chunk.review_status.value,
        retrieved_at=chunk.retrieved_at,
        created_at=chunk.created_at,
        extra_metadata=chunk.metadata,
    )
    metadata["embedding_provider"] = provider
    metadata["embedding_model"] = model
    metadata["embedding_dimension"] = embedding_dimension
    return metadata


def _retrieved_node_from_score_node(node: Any) -> RetrievedNode:
    node_id = getattr(node, "node", None)
    chunk_id = getattr(node_id, "node_id", None) or getattr(node_id, "id_", None)
    if chunk_id is None:
        raise ValueError("Retrieved node did not include a chunk id")
    try:
        chunk_uuid = UUID(str(chunk_id))
    except (TypeError, ValueError) as exc:
        raise ValueError("Retrieved node chunk id was not a valid UUID") from exc
    score = getattr(node, "score", None)
    return RetrievedNode(chunk_id=chunk_uuid, score=float(score) if score is not None else None)


def build_metadata_filter_specs(filters: KnowledgeRetrievalFilters) -> list[MetadataFilterSpec]:
    specs: list[MetadataFilterSpec] = []
    if filters.species_id:
        specs.append(MetadataFilterSpec("species_id", str(filters.species_id)))
    if filters.scientific_name:
        specs.append(MetadataFilterSpec("scientific_name", filters.scientific_name))
    if filters.topic:
        specs.append(MetadataFilterSpec("topic", filters.topic))
    if filters.source_domain:
        specs.append(MetadataFilterSpec("source_domain", filters.source_domain))
    if filters.source_url:
        specs.append(MetadataFilterSpec("source_url", filters.source_url))
    if filters.min_confidence is not None:
        specs.append(
            MetadataFilterSpec("confidence", float(filters.min_confidence), operator=">=")
        )
    if filters.review_status:
        specs.append(
            MetadataFilterSpec("review_status", filters.review_status.value)
        )
    if filters.covered_aspect:
        specs.append(
            MetadataFilterSpec("covered_aspects", filters.covered_aspect)
        )
    if filters.evidence_type:
        specs.append(
            MetadataFilterSpec("evidence_type", filters.evidence_type)
        )
    if filters.source_provenance:
        specs.append(
            MetadataFilterSpec("source_provenance", filters.source_provenance)
        )
    if filters.answerability_status:
        specs.append(
            MetadataFilterSpec("answerability_status", filters.answerability_status)
        )
    if filters.retrieved_after:
        specs.append(
            MetadataFilterSpec("retrieved_at", filters.retrieved_after.isoformat(), operator=">=")
        )
    if filters.retrieved_before:
        specs.append(
            MetadataFilterSpec("retrieved_at", filters.retrieved_before.isoformat(), operator="<=")
        )
    if filters.created_after:
        specs.append(
            MetadataFilterSpec("created_at", filters.created_after.isoformat(), operator=">=")
        )
    if filters.created_before:
        specs.append(
            MetadataFilterSpec("created_at", filters.created_before.isoformat(), operator="<=")
        )
    return specs


def get_pgvector_config(settings: Settings | None = None) -> LlamaIndexPgVectorConfig:
    return build_pgvector_config(settings or get_settings())


def build_llamaindex_metadata_filters(
    filters: KnowledgeRetrievalFilters,
    *,
    metadata_filter_cls: type | None = None,
    metadata_filters_cls: type | None = None,
) -> "Any | None":
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
class LlamaIndexRuntime:
    def __init__(
        self,
        settings: Settings | None = None,
        *,
        vector_store_factory: Callable[[], Any] | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._vector_store_factory = vector_store_factory
        self._vector_store: Any | None = None

    def _get_vector_store(self) -> Any:
        if self._vector_store is None:
            factory = self._vector_store_factory or (
                lambda: create_llamaindex_pgvector_store(self.settings)
            )
            self._vector_store = factory()
        return self._vector_store

    async def _initialize_vector_store(self, store: Any) -> None:
        # PGVectorStore creates its table lazily. Serialize that DDL across
        # workers so two first-time claims cannot race its CREATE TABLE call.
        initialization_engine = store._async_engine
        owns_initialization_engine = initialization_engine is None
        if initialization_engine is None:
            initialization_url = make_url(str(store.connection_string)).set(
                drivername="postgresql+asyncpg"
            )
            initialization_engine = create_async_engine(initialization_url)
        try:
            async with initialization_engine.connect() as connection:
                await connection.execute(
                    text("SELECT pg_advisory_lock(hashtext(:key))"),
                    {"key": "fotosintesis-pgvector-store-initialization"},
                )
                try:
                    await asyncio.to_thread(store._initialize)
                finally:
                    await connection.execute(
                        text("SELECT pg_advisory_unlock(hashtext(:key))"),
                        {"key": "fotosintesis-pgvector-store-initialization"},
                    )
        finally:
            if owns_initialization_engine:
                await initialization_engine.dispose()

    def _build_chunk_from_node(
        self,
        node: Any,
        document: KnowledgeDocumentInput,
        source_lookup: dict[str, Any],
    ) -> KnowledgeChunk:
        metadata = getattr(node, "metadata", {}) or {}
        created_at = metadata.get("created_at")
        if not isinstance(created_at, datetime):
            created_at = datetime.now(timezone.utc)
        return KnowledgeChunk(
            id=UUID(str(node.id_)),
            document_id=None,
            source_id=source_lookup.get(metadata.get("source_url")),
            chunk_index=int(metadata.get("chunk_index", 0)),
            content=node.text,
            metadata=metadata,
            species_id=metadata.get("species_id") or document.species_id,
            scientific_name=metadata.get("scientific_name") or document.scientific_name,
            topic=metadata.get("topic") or document.topic,
            source_domain=metadata.get("source_domain"),
            source_url=metadata.get("source_url"),
            confidence=float(metadata.get("confidence", document.confidence)),
            review_status=ReviewStatus(
                str(metadata.get("review_status", document.review_status.value))
            ),
            retrieved_at=metadata.get("retrieved_at"),
            created_at=created_at,
        )

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
            extra_metadata=document.metadata,
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

    async def index_chunks(
        self,
        *,
        chunks: list[KnowledgeChunk],
        embeddings: list[list[float]],
        provider: str,
        model: str | None,
    ) -> None:
        await self.ensure_nodes(
            chunks=chunks,
            embeddings=embeddings,
            provider=provider,
            model=model,
        )

    async def ensure_nodes(
        self,
        *,
        chunks: list[KnowledgeChunk],
        embeddings: list[list[float]],
        provider: str,
        model: str | None,
    ) -> None:
        try:
            from llama_index.core.schema import TextNode
        except ImportError as exc:
            raise RuntimeError("Install llama-index-core to index knowledge chunks") from exc

        if len(chunks) != len(embeddings):
            raise ValueError("Embedding count must match chunk count")

        nodes = []
        for chunk, embedding in zip(chunks, embeddings, strict=True):
            if chunk.id is None:
                raise ValueError("Cannot index an unsaved chunk")
            metadata = _llamaindex_chunk_metadata(
                chunk,
                provider=provider,
                model=model,
                embedding_dimension=len(embedding),
            )
            node = TextNode(text=chunk.content, id_=str(chunk.id), metadata=metadata)
            node.embedding = embedding
            nodes.append(node)

        store = self._get_vector_store()
        try:
            await self._initialize_vector_store(store)
            table = store._table_class
            schema_name = store.schema_name
            table_name = table.__tablename__
            if not all(
                re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value)
                for value in (schema_name, table_name)
            ):
                raise VectorIndexError("PGVector schema or table identifier is invalid")
            index_hash = hashlib.sha256(
                f"{schema_name}.{table_name}.node_id".encode()
            ).hexdigest()[:16]
            index_name = f"uq_pgvector_node_id_{index_hash}"

            async with store._async_engine.begin() as connection:
                # CREATE INDEX IF NOT EXISTS can still deadlock when two
                # first-time workers issue it concurrently. Keep only this
                # vector DDL/upsert transaction under a database-wide lock.
                await connection.execute(
                    text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
                    {"key": "fotosintesis-pgvector-node-upsert"},
                )
                await connection.execute(
                    text(
                        f'CREATE UNIQUE INDEX IF NOT EXISTS "{index_name}" '
                        f'ON "{schema_name}"."{table_name}" (node_id)'
                    )
                )
                for node in nodes:
                    row = store._node_to_table_row(node)
                    values = {
                        "node_id": row.node_id,
                        "embedding": row.embedding,
                        "text": row.text,
                        "metadata_": row.metadata_,
                    }
                    statement = pg_insert(table).values(**values)
                    statement = statement.on_conflict_do_update(
                        index_elements=[table.node_id],
                        set_={
                            "embedding": statement.excluded.embedding,
                            "text": statement.excluded.text,
                            "metadata_": statement.excluded.metadata_,
                        },
                    )
                    await connection.execute(statement)

            expected_ids = {str(chunk.id) for chunk in chunks}
            actual_nodes = await store.aget_nodes(node_ids=sorted(expected_ids))
            actual_ids = {node.node_id for node in actual_nodes}
            if actual_ids != expected_ids or len(actual_nodes) != len(expected_ids):
                raise VectorIndexIncomplete("PGVector did not contain every expected node")
        except VectorIndexError:
            raise
        except Exception as exc:
            raise VectorIndexError("PGVector node upsert failed") from exc

    async def has_all_nodes(self, node_ids: list[UUID]) -> bool:
        if not node_ids:
            return False
        store = self._get_vector_store()
        expected_ids = {str(node_id) for node_id in node_ids}
        try:
            await self._initialize_vector_store(store)
            nodes = await store.aget_nodes(node_ids=sorted(expected_ids))
        except Exception as exc:
            raise VectorIndexError("PGVector node verification failed") from exc
        return len(nodes) == len(expected_ids) and {
            node.node_id for node in nodes
        } == expected_ids

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
            vector_store=self._get_vector_store(),
            embed_model=create_llamaindex_embed_model(self.settings),
        )
        retriever = index.as_retriever(
            similarity_top_k=limit,
            filters=build_llamaindex_metadata_filters(filters),
        )
        bundle = QueryBundle(query_str=query_text, embedding=query_embedding)
        return [_retrieved_node_from_score_node(node) for node in retriever.retrieve(bundle)]


__all__ = [
    "AppEmbeddingTransform",
    "LlamaIndexPgVectorConfig",
    "LlamaIndexRuntime",
    "MetadataFilterSpec",
    "OrchestratedKnowledgeIngestion",
    "RetrievedNode",
    "VectorIndexError",
    "VectorIndexIncomplete",
    "build_llamaindex_metadata_filters",
    "build_metadata_filter_specs",
    "build_pgvector_config",
    "create_llamaindex_embed_model",
    "create_llamaindex_pgvector_store",
    "get_pgvector_config",
]
