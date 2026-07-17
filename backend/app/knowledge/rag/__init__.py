"""Knowledge RAG package.

Modules under :mod:`app.knowledge.rag` group the LlamaIndex runtime
wiring, filter/embedding plumbing, and the :class:`KnowledgeVectorIndex`
facade into focused modules.
"""

from app.knowledge.rag.embedding import AppEmbeddingTransform, PrecomputedEmbeddingOnly
from app.knowledge.rag.index import KnowledgeVectorIndex
from app.knowledge.rag.runtime import (
    LlamaIndexRuntime,
    build_llamaindex_metadata_filters,
    build_metadata_filter_specs,
    build_pgvector_config,
    create_llamaindex_embed_model,
    create_llamaindex_pgvector_store,
    get_pgvector_config,
)
from app.knowledge.rag.types import (
    LlamaIndexPgVectorConfig,
    MetadataFilterSpec,
    OrchestratedKnowledgeIngestion,
    RetrievedNode,
    VectorIndexError,
    VectorIndexIncomplete,
)

__all__ = [
    "AppEmbeddingTransform",
    "KnowledgeVectorIndex",
    "LlamaIndexPgVectorConfig",
    "LlamaIndexRuntime",
    "MetadataFilterSpec",
    "OrchestratedKnowledgeIngestion",
    "PrecomputedEmbeddingOnly",
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
