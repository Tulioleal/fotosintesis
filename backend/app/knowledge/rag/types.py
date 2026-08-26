"""Shared dataclasses for the knowledge RAG package."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.knowledge.schemas import KnowledgeChunk


class VectorIndexError(RuntimeError):
    pass


class VectorIndexIncomplete(VectorIndexError):
    pass


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


__all__ = [
    "LlamaIndexPgVectorConfig",
    "MetadataFilterSpec",
    "OrchestratedKnowledgeIngestion",
    "RetrievedNode",
    "VectorIndexError",
    "VectorIndexIncomplete",
]
