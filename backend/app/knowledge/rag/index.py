"""KnowledgeVectorIndex facade: ingestion and retrieval over KnowledgeRepository."""

from __future__ import annotations

from app.knowledge.rag.runtime import LlamaIndexRuntime
from app.knowledge.repository import KnowledgeRepository
from app.knowledge.schemas import (
    KnowledgeChunk,
    KnowledgeDocumentInput,
    KnowledgeRetrievalFilters,
    PersistedKnowledgeDocument,
)
from app.providers.interfaces import EmbeddingProvider


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
    ) -> PersistedKnowledgeDocument:
        ingestion = await self.runtime.orchestrate_ingestion(
            document=document,
            embedding_provider=embedding_provider,
        )
        persisted = await self.repository.save_document(
            document, chunks=ingestion.chunks
        )
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
        chunk_ids = [node.chunk_id for node in nodes]
        if not chunk_ids:
            return []
        return list(
            (await self.repository.get_chunks_by_ids(chunk_ids)).values()
        )


__all__ = ["KnowledgeVectorIndex"]
