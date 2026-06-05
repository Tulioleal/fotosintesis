## Purpose

Define how runtime botanical evidence retrieval and trusted knowledge acquisition use LlamaIndex pgvector retrieval, re-embedding and degraded fallback behavior.

## Requirements

### Requirement: Knowledge persistence

The system SHALL persist knowledge documents, sources, chunks and embeddings with required botanical and provenance metadata.

#### Scenario: Knowledge document saved

- **WHEN** new trusted knowledge is ingested
- **THEN** the system stores document content, sources, chunks, embeddings, confidence, review status and timestamps

### Requirement: LlamaIndex pgvector retrieval

The system SHALL use LlamaIndex `PGVectorStore` and `VectorStoreIndex` backed by PostgreSQL + pgvector for runtime botanical evidence retrieval.

#### Scenario: Retrieval by species and topic

- **WHEN** a caller requests evidence for a species and topic
- **THEN** the system retrieves matching chunks through LlamaIndex pgvector retrieval using metadata filters

#### Scenario: SQL-only retrieval path is not used for runtime RAG

- **WHEN** acquisition checks existing evidence or re-runs retrieval after ingestion
- **THEN** the system uses the LlamaIndex-backed retriever instead of direct SQLAlchemy vector scoring

#### Scenario: LlamaIndex dependencies are available

- **WHEN** the backend environment is installed from project dependencies
- **THEN** the LlamaIndex PostgreSQL vector-store integration required by runtime retrieval is installed

### Requirement: Trusted source acquisition

The system MUST restrict incremental acquisition and assistant fallback evidence persistence to approved or explicitly validated trusted sources, regardless of whether search results come from the mock search provider, the configured OpenAI search provider, or assistant fallback web search.

#### Scenario: Untrusted source is sole result

- **WHEN** only blogs, stores, unmoderated forums or non-persistent URLs are available
- **THEN** the system does not use them as the sole basis for persistent knowledge

#### Scenario: OpenAI search returns mixed trust results

- **WHEN** OpenAI-backed search returns both trusted and untrusted source URLs
- **THEN** the acquisition flow uses the existing trusted-source validation rules before persisting or using acquired knowledge

#### Scenario: Assistant fallback persistence receives untrusted web results

- **WHEN** assistant fallback web search returns usable results that fail trusted-source validation
- **THEN** the system does not persist, chunk, embed or index those results as knowledge

#### Scenario: Assistant fallback persistence receives mixed trust results

- **WHEN** assistant fallback web evidence includes both trusted and untrusted source URLs
- **THEN** the system persists, chunks, embeds and indexes only the trusted fallback results through the existing knowledge ingestion path

#### Scenario: Assistant fallback search requests trusted domains

- **WHEN** the assistant runs fallback web search after insufficient RAG evidence
- **THEN** the system passes the configured trusted source domains to the search provider when the provider supports domain filtering

### Requirement: Re-embedding and re-retrieval

The system SHALL create embeddings after successful ingestion, persist them into the LlamaIndex pgvector index with required metadata and allow the caller to re-run retrieval using the new evidence.

#### Scenario: Acquisition succeeds

- **WHEN** a structured knowledge document is generated and persisted
- **THEN** the system chunks, embeds, indexes the chunks through LlamaIndex pgvector and makes them retrievable for the current flow and future flows

#### Scenario: Retrieved evidence maps back to provenance records

- **WHEN** LlamaIndex returns matching vector nodes
- **THEN** the system maps retrieved nodes back to structured knowledge chunks with document, source, confidence, review status and date metadata

### Requirement: Pgvector embedding persistence contract

The system SHALL persist knowledge embedding vectors using a database binding compatible with the PostgreSQL pgvector column type and the configured embedding dimension.

#### Scenario: Embedding vector insert uses pgvector-compatible binding

- **WHEN** a knowledge chunk embedding is persisted to `knowledge_embeddings.embedding_vector`
- **THEN** the insert value is bound or cast as a pgvector-compatible vector value rather than as `VARCHAR`

#### Scenario: Embedding dimension remains validated

- **WHEN** an embedding dimension does not match the configured embedding dimension
- **THEN** the system rejects the embedding before persisting it

### Requirement: JSON formatted acquisition prompt

The system SHALL make structured knowledge acquisition prompts compatible with provider JSON object response formatting.

#### Scenario: OpenAI JSON object formatting is requested

- **WHEN** the acquisition flow calls the configured model provider with JSON object response formatting
- **THEN** the input prompt explicitly instructs the provider to return JSON

### Requirement: Structured API fallback before trusted web acquisition

The system SHALL attempt structured plant-data API evidence after LlamaIndex pgvector retrieval is unavailable or insufficient and before trusted web search/page-fetch acquisition.

#### Scenario: RAG evidence is sufficient

- **WHEN** LlamaIndex pgvector retrieval returns sufficient evidence for the confirmed scientific name and topic
- **THEN** the system answers from retrieved evidence without calling Trefle, Perenual or trusted web search

#### Scenario: RAG evidence is insufficient

- **WHEN** LlamaIndex pgvector retrieval returns no usable chunks or insufficient chunks for the confirmed scientific name and topic
- **THEN** the system attempts structured plant-data lookup before trusted web search

#### Scenario: Structured API evidence is insufficient

- **WHEN** Trefle is unavailable or insufficient and Perenual is unavailable or still insufficient for the requested topic
- **THEN** the system continues to the existing trusted web search/page-fetch fallback

### Requirement: Trusted page fetch safety

The system MUST fetch trusted page evidence only from HTTPS URLs that remain trusted after redirects, and MUST fall back to the trusted search snippet when fetched content is unavailable or unsafe.

#### Scenario: Non-HTTPS URL rejected before fetch

- **WHEN** trusted page evidence is requested for a non-HTTPS URL
- **THEN** the system rejects the page fetch before opening a network request and keeps the trusted snippet available as fallback evidence

#### Scenario: Untrusted URL not fetched

- **WHEN** trusted page evidence is requested for a URL that is not approved or explicitly validated as trusted
- **THEN** the system does not fetch the URL and reports degraded evidence for that result

#### Scenario: Unsupported content type

- **WHEN** a trusted HTTPS page returns a content type outside the supported evidence formats
- **THEN** the system rejects fetched content and keeps the trusted snippet available as fallback evidence

#### Scenario: Oversized response

- **WHEN** a trusted HTTPS page response exceeds the configured maximum response size
- **THEN** the system rejects fetched content and keeps the trusted snippet available as fallback evidence

#### Scenario: Trust-crossing redirect

- **WHEN** a trusted HTTPS page redirects to a URL that is not trusted
- **THEN** the system rejects fetched content and keeps the trusted snippet available as fallback evidence

### Requirement: Trusted fallback page-content acquisition

The system SHALL fetch and extract source page content for fallback web evidence only after each search result passes existing trusted-source validation.

#### Scenario: Trusted page content is fetched for fallback evidence

- **WHEN** fallback web search returns a usable HTTPS result from an approved trusted domain
- **THEN** the system validates the result with the existing trusted-source validator before fetching the page
- **AND** fetches the page using bounded timeouts, response-size limits and content-type checks
- **AND** extracts readable text for use as fallback evidence when extraction succeeds

#### Scenario: Untrusted page is not fetched or persisted

- **WHEN** fallback web search returns a result that does not pass existing trusted-source validation
- **THEN** the system does not fetch the result URL
- **AND** does not include the page content in answer evidence
- **AND** does not persist that result as acquired knowledge

#### Scenario: Unsafe fetch response is rejected

- **WHEN** a trusted result fetch redirects to an untrusted or non-HTTPS URL, exceeds the configured response-size limit, times out, or returns an unsupported content type
- **THEN** the system rejects the fetched page body
- **AND** falls back to the trusted search result snippet for that source without blocking the assistant response

### Requirement: Fetched trusted content ingestion

The system SHALL persist fetched trusted page content through the existing knowledge ingestion and vector-index path when page extraction succeeds.

#### Scenario: Fetched content is persisted as trusted knowledge

- **WHEN** trusted fallback page content is successfully fetched and extracted
- **THEN** the system uses the extracted text as the source evidence for generated knowledge content
- **AND** persists the knowledge document, source metadata, chunks and embeddings through the existing knowledge/vector-index path

#### Scenario: Persistence failure does not block fallback answer

- **WHEN** fetched trusted page content is available but knowledge persistence or embedding fails
- **THEN** the system still returns the fallback assistant answer using available evidence
- **AND** reports the persistence failure as a non-blocking tool failure

### Requirement: Assistant fallback web evidence persistence

The system SHALL persist assistant fallback web evidence through the existing trusted knowledge ingestion path when web-search results are used to answer after insufficient RAG evidence.

#### Scenario: Fallback evidence is ingested

- **WHEN** the assistant answers a botanical question from trusted web-search results because RAG evidence was insufficient
- **THEN** the system builds a knowledge document from the web snippets and source metadata, marks it `auto_ingested`, and ingests it through the LlamaIndex-backed knowledge vector index

#### Scenario: Fallback evidence is embedded and indexed

- **WHEN** fallback web evidence ingestion succeeds
- **THEN** the system chunks, embeds, persists and indexes the evidence using the configured embedding provider so future retrieval can find it

#### Scenario: Fallback evidence persistence is best effort

- **WHEN** fallback evidence ingestion, embedding or indexing fails after usable web evidence was found
- **THEN** the system does not block the assistant answer and records the persistence limitation for observability or response metadata

### Requirement: Snippet degradation remains available

The system SHALL preserve snippet-only fallback behavior when trusted page fetching or extraction fails.

#### Scenario: Extraction fails for trusted result

- **WHEN** a trusted result cannot be fetched or readable text cannot be extracted
- **THEN** the system uses the trusted result title, snippet and URL as degraded fallback evidence
- **AND** does not persist failed or empty fetched page content as knowledge

### Requirement: Acquisition degradation

The system MUST NOT block the user experience completely when structured plant-data lookup, trusted acquisition, trusted page fetching or LlamaIndex pgvector retrieval fails.

#### Scenario: Structured plant-data lookup fails

- **WHEN** structured plant-data providers are unavailable or return insufficient evidence
- **THEN** the system continues to trusted web search/page-fetch fallback before returning a manual search or degraded response

#### Scenario: Trusted acquisition fails

- **WHEN** no trusted source is found or persistence fails after structured plant-data lookup has been attempted where eligible
- **THEN** the system returns the best available partial result with limitations and a retry or manual search path

#### Scenario: Trusted page fetch fails

- **WHEN** a trusted source search result is available but page fetching fails because of network, redirect, content type, size, extraction or implementation errors
- **THEN** the system keeps responding with degraded trusted snippet evidence instead of blocking the assistant response

#### Scenario: LlamaIndex retrieval fails

- **WHEN** the LlamaIndex pgvector retriever cannot query or index evidence
- **THEN** the system attempts eligible structured plant-data lookup and then returns a degraded result with a limitation notice and retry or manual search path instead of silently using SQL-only vector retrieval as the successful path

### Requirement: Failed acquisition rolls back poisoned transactions

The system SHALL roll back failed database work before returning degraded acquisition or fallback results when best-effort knowledge ingestion, embedding persistence or vector indexing fails.

#### Scenario: Trusted acquisition persistence fails after database work starts

- **WHEN** trusted acquisition attempts to persist or index generated knowledge and the operation fails after database work has started
- **THEN** the system rolls back the failed transaction before returning a degraded acquisition result
- **AND** the same request can continue using the database session for later assistant persistence

#### Scenario: Fallback evidence persistence failure is isolated

- **WHEN** fallback web evidence ingestion fails after usable web evidence exists
- **THEN** the system reports the persistence failure as non-blocking tool failure metadata
- **AND** the failed transaction is rolled back before the assistant response is generated or saved

### Requirement: Acquisition failure transaction recovery

The system MUST recover the active database transaction after best-effort knowledge acquisition persistence or embedding failure before continuing with later database writes.

#### Scenario: Best-effort acquisition persistence fails

- **WHEN** trusted knowledge acquisition, embedding persistence or vector indexing fails in a path that continues execution
- **THEN** the system rolls back the failed transaction before performing subsequent database writes

### Requirement: RAG acquisition plant name priority

Runtime botanical retrieval, trusted web fallback, and fallback evidence acquisition SHALL use the assistant operational plant name derived from `plant_binomial_name`, then `plant_scientific_name`, then `plant`.

#### Scenario: RAG retrieval uses binomial name

- **WHEN** an assistant chat request includes `plant_binomial_name` and RAG retrieval is needed
- **THEN** the retrieval query and species/topic context use `plant_binomial_name` as the plant name

#### Scenario: RAG retrieval falls back to scientific name

- **WHEN** RAG retrieval is needed and `plant_binomial_name` is missing but `plant_scientific_name` is present
- **THEN** the retrieval query and species/topic context use `plant_scientific_name` as the plant name

#### Scenario: Trusted web fallback uses operational name

- **WHEN** persisted RAG evidence is insufficient and trusted web fallback runs for a botanical question
- **THEN** the trusted web search query and any fallback evidence ingestion metadata use the assistant operational plant name

#### Scenario: Legacy plant-only acquisition still works

- **WHEN** an assistant chat request includes only `plant` and retrieval or acquisition is needed
- **THEN** RAG retrieval, trusted web fallback, and fallback evidence acquisition use `plant` as the plant name
