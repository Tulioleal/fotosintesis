from datetime import datetime
from enum import Enum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl

from app.providers.types import SearchResult


class ReviewStatus(str, Enum):
    auto_ingested = "auto_ingested"
    needs_review = "needs_review"
    reviewed = "reviewed"
    rejected = "rejected"


class ValidatedClaimIndexStatus(str, Enum):
    pending = "pending"
    complete = "complete"


class AcquisitionStatus(str, Enum):
    retrieved = "retrieved"
    acquired = "acquired"
    degraded = "degraded"


class KnowledgeSourceInput(BaseModel):
    title: str
    url: HttpUrl
    source_domain: str
    retrieved_at: datetime
    published_at: datetime | None = None
    validation_status: str = "trusted"


class KnowledgeDocumentInput(BaseModel):
    scientific_name: str
    topic: str
    title: str
    content: str
    confidence: float = Field(ge=0, le=1)
    review_status: ReviewStatus = ReviewStatus.auto_ingested
    species_id: UUID | None = None
    sources: list[KnowledgeSourceInput]
    metadata: dict[str, object] = Field(default_factory=dict)


class KnowledgeChunk(BaseModel):
    id: UUID | None = None
    document_id: UUID | None = None
    source_id: UUID | None = None
    chunk_index: int
    content: str
    metadata: dict[str, object]
    species_id: UUID | None = None
    scientific_name: str
    topic: str
    source_domain: str
    source_url: str
    confidence: float
    review_status: ReviewStatus
    retrieved_at: datetime
    created_at: datetime | None = None
    score: float | None = None


class KnowledgeRetrievalFilters(BaseModel):
    species_id: UUID | None = None
    scientific_name: str | None = None
    topic: str | None = None
    source_domain: str | None = None
    source_url: str | None = None
    min_confidence: float | None = Field(default=None, ge=0, le=1)
    review_status: ReviewStatus | None = None
    covered_aspect: str | None = None
    evidence_type: str | None = None
    source_provenance: Literal["trusted", "external_fallback"] | None = None
    answerability_status: Literal["full", "partial"] | None = None
    canonical_species_key: str | None = None
    accepted_gbif_key: int | None = Field(default=None, gt=0)
    retrieved_after: datetime | None = None
    retrieved_before: datetime | None = None
    created_after: datetime | None = None
    created_before: datetime | None = None


class PersistedKnowledgeDocument(BaseModel):
    id: UUID
    chunks: list[KnowledgeChunk]


class ValidatedClaimState(BaseModel):
    document_id: UUID
    index_status: ValidatedClaimIndexStatus
    chunks: list[KnowledgeChunk]
    embeddings: list[list[float]]
    embedding_provider: str
    embedding_model: str | None = None


class EnrichmentEvidenceMetadata(BaseModel):
    canonical_species_key: str = Field(min_length=1, max_length=512)
    accepted_gbif_key: int | None = Field(default=None, gt=0)
    normalized_binomial: str = Field(min_length=3, max_length=240)
    canonical_source_url: HttpUrl
    canonical_source_domain: str = Field(min_length=1, max_length=180)
    source_version: str = Field(min_length=1, max_length=255)
    normalized_content_hash: str = Field(min_length=64, max_length=64)
    source_retrieved_at: datetime
    source_published_at: datetime | None = None
    enrichment_provenance: dict[str, object]
    taxonomy_provenance_id: UUID


class EnrichmentEvidenceState(BaseModel):
    document_id: UUID
    chunks: list[KnowledgeChunk]
    embeddings: list[list[float]]
    embedding_provider: str
    embedding_model: str | None = None


class KnowledgeAcquisitionResult(BaseModel):
    status: AcquisitionStatus
    chunks: list[KnowledgeChunk] = Field(default_factory=list)
    document_id: UUID | None = None
    limitations: list[str] = Field(default_factory=list)
    retry_available: bool = False
    manual_search_url: str | None = None
    search_candidates: list[SearchResult] = Field(default_factory=list)
