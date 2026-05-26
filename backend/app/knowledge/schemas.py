from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl


class ReviewStatus(str, Enum):
    auto_ingested = "auto_ingested"
    needs_review = "needs_review"
    reviewed = "reviewed"
    rejected = "rejected"


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
    retrieved_after: datetime | None = None
    retrieved_before: datetime | None = None
    created_after: datetime | None = None
    created_before: datetime | None = None


class PersistedKnowledgeDocument(BaseModel):
    id: UUID
    chunks: list[KnowledgeChunk]


class KnowledgeAcquisitionResult(BaseModel):
    status: AcquisitionStatus
    chunks: list[KnowledgeChunk] = Field(default_factory=list)
    document_id: UUID | None = None
    limitations: list[str] = Field(default_factory=list)
    retry_available: bool = False
    manual_search_url: str | None = None
