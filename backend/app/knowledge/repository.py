from math import sqrt
from uuid import UUID, uuid4

from sqlalchemy import and_, func, insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.tables import (
    enrichment_validation_evidence,
    enrichment_validation_runs,
    knowledge_chunks,
    knowledge_document_aspect_supports,
    knowledge_documents,
    knowledge_embeddings,
    knowledge_sources,
)
from app.core.settings import Settings, get_settings
from app.db.repository import RepositoryBase
from app.knowledge.chunking import chunk_document
from app.knowledge.schemas import (
    EnrichmentEvidenceMetadata,
    EnrichmentEvidenceState,
    KnowledgeChunk,
    KnowledgeDocumentInput,
    KnowledgeRetrievalFilters,
    PersistedKnowledgeDocument,
    ReviewStatus,
    ValidatedClaimIndexStatus,
    ValidatedClaimState,
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
        commit: bool = True,
        ingestion_key: str | None = None,
        document_id: UUID | None = None,
        validated_claim_index_status: ValidatedClaimIndexStatus | None = None,
        enrichment: EnrichmentEvidenceMetadata | None = None,
    ) -> PersistedKnowledgeDocument:
        document_id = document_id or uuid4()
        insert_values = dict(
            id=document_id,
            species_id=document.species_id,
            scientific_name=document.scientific_name,
            topic=document.topic,
            title=document.title,
            content=document.content,
            confidence=document.confidence,
            review_status=document.review_status.value,
        )
        if ingestion_key is not None:
            insert_values["validated_claim_ingestion_key"] = ingestion_key
        if validated_claim_index_status is not None:
            insert_values["validated_claim_index_status"] = validated_claim_index_status.value
        if enrichment is not None:
            insert_values.update(
                canonical_species_key=enrichment.canonical_species_key,
                accepted_gbif_key=enrichment.accepted_gbif_key,
                normalized_binomial=enrichment.normalized_binomial,
                canonical_source_url=str(enrichment.canonical_source_url),
                canonical_source_domain=enrichment.canonical_source_domain,
                source_version=enrichment.source_version,
                normalized_content_hash=enrichment.normalized_content_hash,
                source_retrieved_at=enrichment.source_retrieved_at,
                source_published_at=enrichment.source_published_at,
                enrichment_provenance=enrichment.enrichment_provenance,
                taxonomy_provenance_id=enrichment.taxonomy_provenance_id,
            )
        await self.session.execute(
            insert(knowledge_documents).values(**insert_values)
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
            chunk_id = chunk.id or uuid4()
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

        if commit:
            await self.session.commit()
        return PersistedKnowledgeDocument(id=document_id, chunks=saved_chunks)

    async def add_embeddings(
        self,
        *,
        chunks: list[KnowledgeChunk],
        embeddings: list[list[float]],
        provider: str,
        model: str | None,
        commit: bool = True,
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
        if commit:
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

    async def find_document_by_ingestion_key(self, ingestion_key: str) -> UUID | None:
        row = (
            await self.session.execute(
                select(knowledge_documents.c.id).where(
                    knowledge_documents.c.validated_claim_ingestion_key == ingestion_key
                )
            )
        ).first()
        return row._mapping["id"] if row else None

    async def get_validated_claim_state(
        self, ingestion_key: str
    ) -> ValidatedClaimState | None:
        document = (
            await self.session.execute(
                select(
                    knowledge_documents.c.id,
                    knowledge_documents.c.validated_claim_index_status,
                ).where(
                    knowledge_documents.c.validated_claim_ingestion_key == ingestion_key
                )
            )
        ).mappings().one_or_none()
        if document is None:
            return None
        if document["validated_claim_index_status"] is None:
            raise ValueError("validated claim document is missing index status")

        rows = (
            await self.session.execute(
                select(
                    knowledge_chunks,
                    knowledge_embeddings.c.embedding.label("stored_embedding"),
                    knowledge_embeddings.c.provider.label("embedding_provider"),
                    knowledge_embeddings.c.model.label("embedding_model"),
                )
                .join(
                    knowledge_embeddings,
                    knowledge_embeddings.c.chunk_id == knowledge_chunks.c.id,
                )
                .where(knowledge_chunks.c.document_id == document["id"])
                .order_by(knowledge_chunks.c.chunk_index)
            )
        ).mappings().all()
        if not rows:
            raise ValueError("validated claim document has no persisted chunks and embeddings")

        return ValidatedClaimState(
            document_id=document["id"],
            index_status=ValidatedClaimIndexStatus(
                document["validated_claim_index_status"]
            ),
            chunks=[_row_to_chunk(row) for row in rows],
            embeddings=[list(row["stored_embedding"]) for row in rows],
            embedding_provider=rows[0]["embedding_provider"],
            embedding_model=rows[0]["embedding_model"],
        )

    async def get_enrichment_evidence_state(
        self,
        metadata: EnrichmentEvidenceMetadata,
    ) -> EnrichmentEvidenceState | None:
        document_id = await self.session.scalar(
            select(knowledge_documents.c.id).where(
                knowledge_documents.c.canonical_species_key
                == metadata.canonical_species_key,
                knowledge_documents.c.canonical_source_url
                == str(metadata.canonical_source_url),
                knowledge_documents.c.source_version == metadata.source_version,
                knowledge_documents.c.normalized_content_hash
                == metadata.normalized_content_hash,
            )
        )
        if document_id is None:
            return None
        rows = (
            await self.session.execute(
                select(
                    knowledge_chunks,
                    knowledge_embeddings.c.embedding.label("stored_embedding"),
                    knowledge_embeddings.c.provider.label("embedding_provider"),
                    knowledge_embeddings.c.model.label("embedding_model"),
                )
                .join(
                    knowledge_embeddings,
                    knowledge_embeddings.c.chunk_id == knowledge_chunks.c.id,
                )
                .where(knowledge_chunks.c.document_id == document_id)
                .order_by(knowledge_chunks.c.chunk_index)
            )
        ).mappings().all()
        if not rows:
            raise ValueError("enrichment evidence has no persisted chunks and embeddings")
        return EnrichmentEvidenceState(
            document_id=document_id,
            chunks=[_row_to_chunk(row) for row in rows],
            embeddings=[list(row["stored_embedding"]) for row in rows],
            embedding_provider=rows[0]["embedding_provider"],
            embedding_model=rows[0]["embedding_model"],
        )

    async def add_enrichment_aspect_supports(
        self,
        *,
        document_id: UUID,
        aspects: list[str],
        confidence: float,
        review_status: ReviewStatus,
    ) -> None:
        normalized_aspects = list(dict.fromkeys(aspects))
        for aspect in normalized_aspects:
            await self.session.execute(
                pg_insert(knowledge_document_aspect_supports)
                .values(
                    id=uuid4(),
                    document_id=document_id,
                    aspect=aspect,
                    support_confidence=confidence,
                    review_status=review_status.value,
                )
                .on_conflict_do_nothing(
                    index_elements=[
                        knowledge_document_aspect_supports.c.document_id,
                        knowledge_document_aspect_supports.c.aspect,
                    ]
                )
            )
        chunk_rows = (
            await self.session.execute(
                select(knowledge_chunks.c.id, knowledge_chunks.c.metadata).where(
                    knowledge_chunks.c.document_id == document_id
                )
            )
        ).mappings().all()
        for row in chunk_rows:
            metadata = dict(row["metadata"] or {})
            metadata["covered_aspects"] = list(
                dict.fromkeys(
                    [
                        *(metadata.get("covered_aspects") or []),
                        *normalized_aspects,
                    ]
                )
            )
            await self.session.execute(
                update(knowledge_chunks)
                .where(knowledge_chunks.c.id == row["id"])
                .values(metadata=metadata)
            )

    async def add_enrichment_validation_run(
        self,
        *,
        validation_id: UUID,
        job_id: UUID,
        taxonomy_provenance_id: UUID,
        policy_version: int,
        required_aspects: list[str],
        covered_aspects: list[str],
        missing_aspects: list[str],
        answerability_status: str,
        judge_confidence: float,
        validation_metadata: dict[str, object],
        document_ids: list[UUID] | None = None,
    ) -> None:
        await self.session.execute(
            pg_insert(enrichment_validation_runs)
            .values(
                id=validation_id,
                job_id=job_id,
                taxonomy_provenance_id=taxonomy_provenance_id,
                policy_version=policy_version,
                required_aspects=required_aspects,
                covered_aspects=covered_aspects,
                missing_aspects=missing_aspects,
                answerability_status=answerability_status,
                judge_confidence=judge_confidence,
                validation_metadata=validation_metadata,
            )
            .on_conflict_do_nothing(index_elements=[enrichment_validation_runs.c.id])
        )

        if document_ids:
            for document_id in dict.fromkeys(document_ids):
                await self.session.execute(
                    pg_insert(enrichment_validation_evidence)
                    .values(
                        id=uuid4(),
                        validation_run_id=validation_id,
                        document_id=document_id,
                    )
                    .on_conflict_do_nothing(
                        index_elements=[
                            enrichment_validation_evidence.c.validation_run_id,
                            enrichment_validation_evidence.c.document_id,
                        ]
                    )
                )

    async def mark_validated_claim_index_complete(self, document_id: UUID) -> None:
        result = await self.session.execute(
            update(knowledge_documents)
            .where(
                knowledge_documents.c.id == document_id,
                knowledge_documents.c.validated_claim_index_status.in_(
                    [
                        ValidatedClaimIndexStatus.pending.value,
                        ValidatedClaimIndexStatus.complete.value,
                    ]
                ),
            )
            .values(
                validated_claim_index_status=ValidatedClaimIndexStatus.complete.value,
                updated_at=func.now(),
            )
        )
        if result.rowcount != 1:
            raise ValueError("validated claim document was not available for completion")

    async def set_document_ingestion_key(
        self, *, document_id: UUID, ingestion_key: str
    ) -> None:
        await self.session.execute(
            update(knowledge_documents)
            .where(knowledge_documents.c.id == document_id)
            .values(validated_claim_ingestion_key=ingestion_key)
        )

    async def get_chunks_by_ids(self, chunk_ids: list[UUID]) -> dict[UUID, KnowledgeChunk]:
        if not chunk_ids:
            return {}
        rows = (
            await self.session.execute(
                select(knowledge_chunks).where(knowledge_chunks.c.id.in_(chunk_ids))
            )
        ).all()
        chunks: dict[UUID, KnowledgeChunk] = {
            row.id: _row_to_chunk(row._mapping) for row in rows
        }
        enrichment_doc_ids: set[UUID] = set()
        enrichment_chunk_ids: list[UUID] = []
        for chunk_id, chunk in chunks.items():
            if chunk.metadata.get("canonical_species_key"):
                doc_id = chunk.document_id
                if doc_id is not None:
                    enrichment_doc_ids.add(doc_id)
                    enrichment_chunk_ids.append(chunk_id)

        if not enrichment_doc_ids:
            return chunks

        doc_rows = (
            await self.session.execute(
                select(
                    knowledge_documents.c.id,
                    knowledge_documents.c.canonical_species_key,
                    knowledge_documents.c.accepted_gbif_key,
                    knowledge_documents.c.normalized_binomial,
                    knowledge_documents.c.source_retrieved_at,
                    knowledge_documents.c.source_published_at,
                    knowledge_documents.c.taxonomy_provenance_id,
                ).where(knowledge_documents.c.id.in_(enrichment_doc_ids))
            )
        ).mappings().all()
        docs_by_id = {row["id"]: row for row in doc_rows}

        aspect_rows = (
            await self.session.execute(
                select(
                    knowledge_document_aspect_supports.c.document_id,
                    knowledge_document_aspect_supports.c.aspect,
                ).where(
                    knowledge_document_aspect_supports.c.document_id.in_(
                        enrichment_doc_ids
                    )
                )
            )
        ).mappings().all()
        aspects_by_doc: dict[UUID, list[str]] = {}
        for row in aspect_rows:
            aspects_by_doc.setdefault(row["document_id"], []).append(row["aspect"])

        validation_rows = (
            await self.session.execute(
                select(
                    enrichment_validation_evidence.c.document_id,
                    enrichment_validation_runs.c.id.label("validation_run_id"),
                    enrichment_validation_runs.c.answerability_status,
                    enrichment_validation_runs.c.covered_aspects,
                    enrichment_validation_runs.c.created_at.label("validated_at"),
                )
                .select_from(enrichment_validation_evidence)
                .join(
                    enrichment_validation_runs,
                    enrichment_validation_runs.c.id
                    == enrichment_validation_evidence.c.validation_run_id,
                )
                .where(
                    enrichment_validation_evidence.c.document_id.in_(
                        enrichment_doc_ids
                    ),
                    enrichment_validation_runs.c.answerability_status.in_(
                        ["full", "partial"]
                    ),
                )
            )
        ).mappings().all()
        validations_by_doc: dict[UUID, list[dict[str, object]]] = {}
        for row in validation_rows:
            validations_by_doc.setdefault(row["document_id"], []).append(
                {
                    "validation_run_id": str(row["validation_run_id"]),
                    "status": row["answerability_status"],
                    "validated_at": row["validated_at"].isoformat(),
                    "covered_aspects": list(row["covered_aspects"])
                    if isinstance(row["covered_aspects"], list)
                    else [],
                }
            )

        for chunk_id in enrichment_chunk_ids:
            chunk = chunks[chunk_id]
            doc_id = chunk.document_id
            if doc_id is None:
                continue
            doc = docs_by_id.get(doc_id)
            if doc is None:
                continue
            validations = validations_by_doc.get(doc_id)
            if not validations:
                del chunks[chunk_id]
                continue
            supported_aspects = aspects_by_doc.get(doc_id, [])
            metadata = dict(chunk.metadata)
            metadata.update(
                {
                    "canonical_species_key": doc["canonical_species_key"],
                    "accepted_gbif_key": doc["accepted_gbif_key"],
                    "normalized_binomial": doc["normalized_binomial"],
                    "source_retrieved_at": (
                        doc["source_retrieved_at"].isoformat()
                        if doc["source_retrieved_at"]
                        else None
                    ),
                    "source_published_at": (
                        doc["source_published_at"].isoformat()
                        if doc["source_published_at"]
                        else None
                    ),
                    "taxonomy_provenance_id": (
                        str(doc["taxonomy_provenance_id"])
                        if doc["taxonomy_provenance_id"]
                        else None
                    ),
                    "covered_aspects": supported_aspects,
                    "validation_provenance": validations,
                }
            )
            chunks[chunk_id] = chunk.model_copy(update={"metadata": metadata})

        return chunks


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
    if filters.source_provenance:
        conditions.append(
            knowledge_chunks.c.metadata["source_provenance"].as_string()
            == filters.source_provenance
        )
    if filters.answerability_status:
        conditions.append(
            knowledge_chunks.c.metadata["answerability_status"].as_string()
            == filters.answerability_status
        )
    if filters.canonical_species_key:
        conditions.append(
            knowledge_chunks.c.metadata["canonical_species_key"].as_string()
            == filters.canonical_species_key
        )
    if filters.accepted_gbif_key is not None:
        conditions.append(
            knowledge_chunks.c.metadata["accepted_gbif_key"].as_string()
            == str(filters.accepted_gbif_key)
        )
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
