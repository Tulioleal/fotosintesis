from datetime import datetime
from uuid import UUID

from app.knowledge.schemas import KnowledgeChunk, KnowledgeDocumentInput


CHUNK_EXTRA_METADATA_KEYS = {
    "required_aspects",
    "covered_aspects",
    "missing_aspects",
    "language",
    "evidence_type",
    "answerability_status",
    "source_provenance",
    "validation_confidence",
    "source_support_claim",
    "source_support_quote",
    "persisted_from",
    "claim_ingestion_key",
    "ingestion_policy_version",
}


def chunk_document(
    document: KnowledgeDocumentInput,
    *,
    chunk_size: int = 900,
    overlap: int = 120,
) -> list[KnowledgeChunk]:
    if not document.sources:
        raise ValueError("Knowledge documents require at least one trusted source")
    if chunk_size <= overlap:
        raise ValueError("chunk_size must be greater than overlap")

    source = document.sources[0]
    content = " ".join(document.content.split())
    if not content:
        raise ValueError("Knowledge document content cannot be empty")

    chunks: list[KnowledgeChunk] = []
    start = 0
    while start < len(content):
        text = content[start : start + chunk_size].strip()
        if text:
            chunks.append(
                _build_chunk(
                    document,
                    chunk_index=len(chunks),
                    content=text,
                    source_domain=source.source_domain,
                    source_url=str(source.url),
                    retrieved_at=source.retrieved_at,
                )
            )
        start += chunk_size - overlap
    return chunks


def build_chunk_metadata(
    *,
    species_id: UUID | None,
    scientific_name: str,
    topic: str,
    source_domain: str,
    source_url: str,
    confidence: float,
    review_status: str,
    retrieved_at: datetime,
    created_at: datetime | None = None,
    extra_metadata: dict[str, object] | None = None,
) -> dict[str, object]:
    metadata = {
        "species_id": str(species_id) if species_id else None,
        "scientific_name": scientific_name,
        "topic": topic,
        "source_domain": source_domain,
        "source_url": source_url,
        "confidence": confidence,
        "review_status": review_status,
        "retrieved_at": retrieved_at.isoformat(),
        "created_at": created_at.isoformat() if created_at else None,
    }
    metadata.update(
        {
            key: value
            for key, value in (extra_metadata or {}).items()
            if key in CHUNK_EXTRA_METADATA_KEYS
        }
    )
    return metadata


def _build_chunk(
    document: KnowledgeDocumentInput,
    *,
    chunk_index: int,
    content: str,
    source_domain: str,
    source_url: str,
    retrieved_at: datetime,
) -> KnowledgeChunk:
    return KnowledgeChunk(
        chunk_index=chunk_index,
        content=content,
        metadata=build_chunk_metadata(
            species_id=document.species_id,
            scientific_name=document.scientific_name,
            topic=document.topic,
            source_domain=source_domain,
            source_url=source_url,
            confidence=document.confidence,
            review_status=document.review_status.value,
            retrieved_at=retrieved_at,
            extra_metadata=document.metadata,
        ),
        species_id=document.species_id,
        scientific_name=document.scientific_name,
        topic=document.topic,
        source_domain=source_domain,
        source_url=source_url,
        confidence=document.confidence,
        review_status=document.review_status,
        retrieved_at=retrieved_at,
    )
