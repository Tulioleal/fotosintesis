"""KnowledgeVectorIndex facade: ingestion and retrieval over KnowledgeRepository."""

from __future__ import annotations

from uuid import UUID

from app.knowledge.rag.runtime import LlamaIndexRuntime
from app.knowledge.rag.types import OrchestratedKnowledgeIngestion
from app.knowledge.repository import KnowledgeRepository
from app.knowledge.schemas import (
    KnowledgeChunk,
    KnowledgeDocumentInput,
    EnrichmentEvidenceMetadata,
    KnowledgeRetrievalFilters,
    PersistedKnowledgeDocument,
    ValidatedClaimIndexStatus,
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
        commit: bool = True,
        ingestion_key: str | None = None,
        document_id: UUID | None = None,
        chunks: list[KnowledgeChunk] | None = None,
    ) -> PersistedKnowledgeDocument:
        ingestion = await self.prepare_document(
            document,
            embedding_provider=embedding_provider,
        )
        provided_chunks = list(chunks) if chunks is not None else ingestion.chunks
        persisted = await self.repository.save_document(
            document,
            chunks=provided_chunks,
            commit=False,
            ingestion_key=ingestion_key,
            document_id=document_id,
            validated_claim_index_status=(
                ValidatedClaimIndexStatus.pending if ingestion_key else None
            ),
        )
        await self.repository.add_embeddings(
            chunks=persisted.chunks,
            embeddings=ingestion.embeddings,
            provider=ingestion.provider,
            model=ingestion.model,
            commit=False,
        )
        if commit:
            await self.repository.session.commit()
        await self.ensure_vector_nodes(
            chunks=persisted.chunks,
            embeddings=ingestion.embeddings,
            provider=ingestion.provider,
            model=ingestion.model,
        )
        return persisted

    async def prepare_document(
        self,
        document: KnowledgeDocumentInput,
        *,
        embedding_provider: EmbeddingProvider,
    ) -> OrchestratedKnowledgeIngestion:
        return await self.runtime.orchestrate_ingestion(
            document=document,
            embedding_provider=embedding_provider,
        )

    async def persist_relational(
        self,
        document: KnowledgeDocumentInput,
        *,
        ingestion: OrchestratedKnowledgeIngestion,
        ingestion_key: str,
        document_id: UUID,
    ) -> PersistedKnowledgeDocument:
        persisted = await self.repository.save_document(
            document,
            chunks=ingestion.chunks,
            commit=False,
            ingestion_key=ingestion_key,
            document_id=document_id,
            validated_claim_index_status=ValidatedClaimIndexStatus.pending,
        )
        await self.repository.add_embeddings(
            chunks=persisted.chunks,
            embeddings=ingestion.embeddings,
            provider=ingestion.provider,
            model=ingestion.model,
            commit=False,
        )
        await self.repository.session.commit()
        return persisted

    async def persist_enrichment_relational(
        self,
        document: KnowledgeDocumentInput,
        *,
        ingestion: OrchestratedKnowledgeIngestion,
        enrichment: EnrichmentEvidenceMetadata,
        document_id: UUID,
    ) -> PersistedKnowledgeDocument:
        persisted = await self.repository.save_document(
            document,
            chunks=ingestion.chunks,
            commit=False,
            document_id=document_id,
            enrichment=enrichment,
        )
        await self.repository.add_embeddings(
            chunks=persisted.chunks,
            embeddings=ingestion.embeddings,
            provider=ingestion.provider,
            model=ingestion.model,
            commit=False,
        )
        return persisted

    async def ensure_vector_nodes(
        self,
        *,
        chunks: list[KnowledgeChunk],
        embeddings: list[list[float]],
        provider: str,
        model: str | None,
    ) -> None:
        await self.runtime.ensure_nodes(
            chunks=chunks,
            embeddings=embeddings,
            provider=provider,
            model=model,
        )

    async def has_all_nodes(self, chunk_ids: list[UUID]) -> bool:
        return await self.runtime.has_all_nodes(chunk_ids)

    async def mark_index_complete(self, document_id: UUID) -> None:
        await self.repository.mark_validated_claim_index_complete(document_id)
        await self.repository.session.commit()

    async def index_chunks(
        self,
        *,
        chunks: list[KnowledgeChunk],
        embeddings: list[list[float]],
        provider: str,
        model: str | None,
    ) -> None:
        await self.runtime.index_chunks(
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
        by_id = await self.repository.get_chunks_by_ids(chunk_ids)
        return [
            by_id[node.chunk_id].model_copy(update={"score": node.score})
            for node in nodes
            if node.chunk_id in by_id
        ]


__all__ = ["KnowledgeVectorIndex"]
