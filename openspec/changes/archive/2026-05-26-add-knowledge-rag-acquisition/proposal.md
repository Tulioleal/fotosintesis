## Why

Fotosintesis AI needs evidence-backed botanical knowledge that can grow over time. This change creates the persistence, retrieval and incremental acquisition layer used by profiles and the assistant.

## What Changes

- Implement knowledge document, source, chunk and embedding persistence models.
- Configure LlamaIndex with PostgreSQL + pgvector retrieval.
- Implement chunking with required metadata for species, topic, source, confidence, review status and dates.
- Implement retrieval filters by species, topic, source, confidence, review status and date.
- Implement trusted source search constrained to approved domains and validation rules.
- Implement structured knowledge document generation with sources, confidence and `auto_ingested` review status.
- Implement embedding creation and re-retrieval after successful ingestion.
- Implement degradation when trusted acquisition fails.

## Capabilities

### New Capabilities

- `knowledge-rag-acquisition`: knowledge persistence, metadata retrieval, trusted acquisition, embeddings and degradation.

### Modified Capabilities

- None.

## Impact

- Affects backend knowledge models, LlamaIndex integration, vector search, source validation, ingestion workflows and retrieval APIs/services.
