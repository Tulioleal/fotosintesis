from math import sqrt
from uuid import UUID, uuid4

from sqlalchemy import and_, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.tables import (
    knowledge_chunks,
    knowledge_documents,
    knowledge_embeddings,
    knowledge_sources,
)
from app.core.settings import Settings, get_settings
from app.db.repository import RepositoryBase
from app.knowledge.chunking import chunk_document
from app.knowledge.schemas import (
    KnowledgeChunk,
    KnowledgeDocumentInput,
    KnowledgeRetrievalFilters,
    PersistedKnowledgeDocument,
    ReviewStatus,
)


class KnowledgeRepository(RepositoryBase):
    def __init__(self, session: AsyncSession, settings: Settings | None = None) -> None:
        super().__init__(session)
        self.settings = settings or get_settings()

    async def save_document(
        self,
        document: KnowledgeDocumentInput,
        *,
        chunks: list[KnowledgeChunk] | None = None,
    ) -> PersistedKnowledgeDocument:
        document_id = uuid4()
        await self.session.execute(
            insert(knowledge_documents).values(
                id=document_id,
                species_id=document.species_id,
                scientific_name=document.scientific_name,
                topic=document.topic,
                title=document.title,
                content=document.content,
                confidence=document.confidence,
                review_status=document.review_status.value,
            )
        )

        source_ids: dict[str, UUID] = {}
        for source in document.sources:
            source_id = uuid4()
            source_ids[str(source.url)] = source_id
            await self.session.execute(
                insert(knowledge_sources).values(
                    id=source_id,
                    document_id=document_id,
                    title=source.title,
                    url=str(source.url),
                    source_domain=source.source_domain,
                    retrieved_at=source.retrieved_at,
                    published_at=source.published_at,
                    validation_status=source.validation_status,
                )
            )

        saved_chunks: list[KnowledgeChunk] = []
        for chunk in chunks or chunk_document(document):
            chunk_id = uuid4()
            source_id = source_ids.get(chunk.source_url)
            await self.session.execute(
                insert(knowledge_chunks).values(
                    id=chunk_id,
                    document_id=document_id,
                    source_id=source_id,
                    chunk_index=chunk.chunk_index,
                    content=chunk.content,
                    metadata=chunk.metadata,
                    species_id=chunk.species_id,
                    scientific_name=chunk.scientific_name,
                    topic=chunk.topic,
                    source_domain=chunk.source_domain,
                    source_url=chunk.source_url,
                    confidence=chunk.confidence,
                    review_status=chunk.review_status.value,
                    retrieved_at=chunk.retrieved_at,
                )
            )
            saved_chunks.append(
                chunk.model_copy(
                    update={"id": chunk_id, "document_id": document_id, "source_id": source_id}
                )
            )

        await self.session.commit()
        return PersistedKnowledgeDocument(id=document_id, chunks=saved_chunks)

    async def add_embeddings(
        self,
        *,
        chunks: list[KnowledgeChunk],
        embeddings: list[list[float]],
        provider: str,
        model: str | None,
    ) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError("Embedding count must match chunk count")

        for chunk, embedding in zip(chunks, embeddings, strict=True):
            if chunk.id is None:
                raise ValueError("Cannot store embedding for an unsaved chunk")
            self._validate_embedding_dimension(embedding)
            await self.session.execute(
                insert(knowledge_embeddings).values(
                    id=uuid4(),
                    chunk_id=chunk.id,
                    provider=provider,
                    model=model,
                    embedding=embedding,
                    embedding_vector=embedding,
                    embedding_dimension=len(embedding),
                )
            )
        await self.session.commit()

    def _validate_embedding_dimension(self, embedding: list[float]) -> None:
        expected_dimension = self.settings.embedding_dimension
        if len(embedding) != expected_dimension:
            raise ValueError(
                "Embedding dimension mismatch: "
                f"expected {expected_dimension}, got {len(embedding)}"
            )

    async def retrieve_chunks(
        self,
        filters: KnowledgeRetrievalFilters,
        *,
        query_embedding: list[float] | None = None,
        limit: int = 5,
    ) -> list[KnowledgeChunk]:
        conditions = _build_filter_conditions(filters)
        statement = select(
            knowledge_chunks, knowledge_embeddings.c.embedding.label("embedding")
        ).outerjoin(
            knowledge_embeddings, knowledge_embeddings.c.chunk_id == knowledge_chunks.c.id
        )
        if conditions:
            statement = statement.where(and_(*conditions))
        statement = statement.order_by(knowledge_chunks.c.created_at.desc()).limit(
            max(limit * 4, limit)
        )

        rows = (await self.session.execute(statement)).all()
        chunks: list[KnowledgeChunk] = []
        for row in rows:
            chunk = _row_to_chunk(row._mapping)
            embedding = row._mapping.get("embedding")
            if query_embedding and embedding:
                chunk = chunk.model_copy(
                    update={"score": _cosine_similarity(query_embedding, embedding)}
                )
            chunks.append(chunk)

        if query_embedding:
            chunks.sort(
                key=lambda item: item.score if item.score is not None else -1,
                reverse=True,
            )
        return chunks[:limit]

    async def get_chunks_by_ids(self, chunk_ids: list[UUID]) -> dict[UUID, KnowledgeChunk]:
        if not chunk_ids:
            return {}
        rows = (
            await self.session.execute(
                select(knowledge_chunks).where(knowledge_chunks.c.id.in_(chunk_ids))
            )
        ).all()
        return {row.id: _row_to_chunk(row._mapping) for row in rows}


def _build_filter_conditions(filters: KnowledgeRetrievalFilters) -> list:
    conditions = []
    if filters.species_id:
        conditions.append(knowledge_chunks.c.species_id == filters.species_id)
    if filters.scientific_name:
        conditions.append(knowledge_chunks.c.scientific_name == filters.scientific_name)
    if filters.topic:
        conditions.append(knowledge_chunks.c.topic == filters.topic)
    if filters.source_domain:
        conditions.append(knowledge_chunks.c.source_domain == filters.source_domain)
    if filters.source_url:
        conditions.append(knowledge_chunks.c.source_url == filters.source_url)
    if filters.min_confidence is not None:
        conditions.append(knowledge_chunks.c.confidence >= filters.min_confidence)
    if filters.review_status:
        conditions.append(knowledge_chunks.c.review_status == filters.review_status.value)
    if filters.covered_aspect:
        conditions.append(knowledge_chunks.c.metadata["covered_aspects"].contains(filters.covered_aspect))
    if filters.evidence_type:
        conditions.append(knowledge_chunks.c.metadata["evidence_type"].as_string() == filters.evidence_type)
    if filters.retrieved_after:
        conditions.append(knowledge_chunks.c.retrieved_at >= filters.retrieved_after)
    if filters.retrieved_before:
        conditions.append(knowledge_chunks.c.retrieved_at <= filters.retrieved_before)
    if filters.created_after:
        conditions.append(knowledge_chunks.c.created_at >= filters.created_after)
    if filters.created_before:
        conditions.append(knowledge_chunks.c.created_at <= filters.created_before)
    return conditions


def _row_to_chunk(row: dict) -> KnowledgeChunk:
    return KnowledgeChunk(
        id=row["id"],
        document_id=row["document_id"],
        source_id=row["source_id"],
        chunk_index=row["chunk_index"],
        content=row["content"],
        metadata=row["metadata"],
        species_id=row["species_id"],
        scientific_name=row["scientific_name"],
        topic=row["topic"],
        source_domain=row["source_domain"],
        source_url=row["source_url"],
        confidence=row["confidence"],
        review_status=ReviewStatus(row["review_status"]),
        retrieved_at=row["retrieved_at"],
        created_at=row["created_at"],
    )


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    size = min(len(left), len(right))
    if size == 0:
        return 0.0
    left = left[:size]
    right = right[:size]
    numerator = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = sqrt(sum(a * a for a in left))
    right_norm = sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return numerator / (left_norm * right_norm)
