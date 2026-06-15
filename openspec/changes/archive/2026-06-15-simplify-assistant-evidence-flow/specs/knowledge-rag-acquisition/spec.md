## MODIFIED Requirements

### Requirement: LlamaIndex pgvector retrieval

The system SHALL use LlamaIndex `PGVectorStore` and `VectorStoreIndex` backed by PostgreSQL + pgvector for runtime botanical evidence retrieval. Runtime assistant retrieval SHALL construct an enriched query from confirmed taxonomy, classified topic, requested required aspects, and the original user question while continuing to use metadata filters where applicable.

#### Scenario: Retrieval by species, topic and requested question

- **WHEN** a caller requests evidence for a species, topic, required aspects and user question
- **THEN** the system retrieves matching chunks through LlamaIndex pgvector retrieval using metadata filters and an enriched text query
- **AND** the enriched text query includes confirmed taxonomy, topic, required aspects and the original user question

#### Scenario: SQL-only retrieval path is not used for runtime RAG

- **WHEN** acquisition checks existing evidence or re-runs retrieval after ingestion
- **THEN** the system uses the LlamaIndex-backed retriever instead of direct SQLAlchemy vector scoring

#### Scenario: LlamaIndex dependencies are available

- **WHEN** the backend environment is installed from project dependencies
- **THEN** the LlamaIndex PostgreSQL vector-store integration required by runtime retrieval is installed

#### Scenario: Query does not rely only on topic

- **WHEN** a user asks a specific plant-care question whose wording is more specific than the classified topic
- **THEN** retrieval includes the original question and required aspects in the query text
- **AND** topic alone is not the only semantic retrieval term

### Requirement: Aspect-aware evidence validation

Runtime botanical evidence retrieval and fallback evidence acquisition SHALL validate evidence against the requested plant-care `required_aspects` before the evidence can be treated as answerable. Validation SHALL use semantic judging as the authority for aspect coverage and SHALL return answerability status, covered aspects, missing aspects, source support, contradictions, reason and confidence. The system MUST structurally validate judge output and degrade incoherent results to a safer status before answer synthesis or persistence.

#### Scenario: Generic care evidence fails specific aspect validation

- **WHEN** retrieved RAG evidence contains generic plant-care information but does not directly cover the requested watering frequency aspect
- **THEN** evidence validation does not mark `watering_frequency_or_trigger` as covered
- **AND** the evidence is not treated as full for that aspect

#### Scenario: Covered aspects constrained to request

- **WHEN** evidence validation returns covered aspects
- **THEN** every covered aspect is a subset of the requested `required_aspects`

#### Scenario: Missing aspects make evidence partial

- **WHEN** validation covers only some requested required aspects
- **THEN** the validation result marks the uncovered requested aspects as missing
- **AND** the validation result uses `status: "partial"`

#### Scenario: Low-confidence validation rejected

- **WHEN** validation confidence is below the configured evidence validation threshold
- **THEN** the evidence is treated as insufficient for the requested aspects

#### Scenario: Safety-sensitive validation uses higher threshold

- **WHEN** the requested aspect is safety-sensitive, including pet toxicity or human edibility
- **THEN** validation requires direct evidence and the configured safety-sensitive threshold before marking the aspect covered

#### Scenario: Deterministic keyword mismatch does not block semantic support

- **WHEN** semantic judging validates a requested aspect with coherent source support
- **AND** hardcoded keyword matching would fail because of language, synonyms, spelling variants or source phrasing
- **THEN** deterministic keyword mismatch does not reject the evidence as a blocking decision

#### Scenario: Incoherent full result degrades

- **WHEN** judge output declares `status: "full"` but omits required aspect coverage, source support, or adequate confidence
- **THEN** the system degrades the status to `partial` or `insufficient`
- **AND** the degraded result is not persisted unless source support remains structurally valid

#### Scenario: Contradictory result requires source evidence

- **WHEN** judge output declares `status: "contradictory"`
- **THEN** contradictions include source URLs for conflicting claims
- **AND** missing contradiction source URLs degrade the result to `insufficient`

### Requirement: Targeted missing-aspect web fallback

Trusted web fallback for assistant plant-care answers SHALL run after local evidence validation fails to return `full`. Web search SHALL use confirmed taxonomy, topic, required aspects, and the original user question, and SHALL exclude nicknames, display names, and classifier plant references from search construction.

#### Scenario: RAG covers no requested aspects

- **WHEN** local RAG validation covers none of the requested required aspects
- **THEN** trusted web fallback searches for all requested required aspects using confirmed taxonomy and the original user question

#### Scenario: RAG covers some requested aspects

- **WHEN** local RAG validation covers some requested required aspects and leaves others missing
- **THEN** trusted web fallback searches using confirmed taxonomy, missing aspects, and the original user question before final answer synthesis

#### Scenario: RAG contradictory triggers web fallback

- **WHEN** local RAG validation reports contradictory evidence for requested required aspects
- **THEN** trusted web fallback searches for the affected aspects using confirmed taxonomy and the original user question

#### Scenario: Search query excludes display name

- **WHEN** the display plant name differs from confirmed taxonomy
- **THEN** trusted web fallback query construction uses `plant_binomial_name` or `plant_scientific_name` and does not use the display name, nickname, apodo, or classifier plant reference

#### Scenario: Web fallback skipped when local evidence full

- **WHEN** local evidence validation covers all requested required aspects above threshold with `status: "full"`
- **THEN** trusted web fallback is not called for that answer

### Requirement: Validated web evidence persistence metadata

The system SHALL persist assistant web fallback evidence only as small validated claim documents derived from final judge `source_support`. Persisted validated web claim evidence SHALL include filterable metadata for confirmed taxonomy, topic, required aspects, covered aspects, language, evidence type, final answerability status, validation confidence, source claim, source quote, source domain when available, review status, and source provenance.

#### Scenario: Validated web claim is persisted with covered aspects

- **WHEN** final combined judging returns source support for one or more requested required aspects with `status: "full"`
- **THEN** the system persists, chunks, embeds, and indexes only the validated source-supported claims
- **AND** persisted metadata includes `covered_aspects`, `required_aspects`, `topic`, `language`, `evidence_type: "validated_web_claim"`, final answerability status, validation confidence, source claim, source quote, source domain when available, `persisted_from: "assistant_final_judge"`, and `review_status: "auto_ingested"`

#### Scenario: Safe partial web claim is persisted

- **WHEN** final combined judging returns `status: "partial"` with clear source support for at least one requested aspect
- **THEN** the system persists only the source-supported claims for covered aspects
- **AND** persisted metadata identifies the final status as partial and includes missing aspects when available

#### Scenario: Unvalidated web evidence is not persisted

- **WHEN** web evidence is selected by search but lacks final judge source support or falls below the validation threshold
- **THEN** the system does not persist, chunk, embed, or index that evidence

#### Scenario: Insufficient evidence is not persisted

- **WHEN** final combined judging returns `status: "insufficient"`
- **THEN** the system does not persist, chunk, embed, or index source packages from that answer path

#### Scenario: Contradictory evidence is not persisted

- **WHEN** final combined judging returns `status: "contradictory"`
- **THEN** the system does not persist, chunk, embed, or index the conflicting evidence as knowledge

#### Scenario: General guidance is not persisted

- **WHEN** the assistant answer includes conservative general guidance that is not source-validated for the specific plant/question
- **THEN** the system does not persist, chunk, embed, or index that guidance

#### Scenario: Final assistant answer text is not persisted as knowledge

- **WHEN** the assistant returns a final answer to the user
- **THEN** the knowledge acquisition path does not persist the final assistant response text as a knowledge document

#### Scenario: Validated web claim remains filterable

- **WHEN** validated web claim evidence is persisted
- **THEN** future retrieval can filter or constrain results by confirmed taxonomy, topic, covered aspects, review status, evidence type, final answerability status, and source domain when available

### Requirement: Structured API fallback before trusted web acquisition

The system SHALL NOT attempt structured plant-data API evidence in the normal assistant chat-time plant-care answer path after LlamaIndex pgvector retrieval is unavailable, partial, insufficient, or contradictory. Structured plant-data providers MAY remain available for backend services, tests, and future offline acquisition flows outside this chat-time path.

#### Scenario: RAG evidence is sufficient

- **WHEN** LlamaIndex pgvector retrieval returns full evidence for the confirmed scientific name and requested aspects
- **THEN** the system answers from retrieved evidence without calling Trefle, Perenual or trusted web search

#### Scenario: RAG evidence is not full

- **WHEN** LlamaIndex pgvector retrieval returns no usable chunks, partial chunks, insufficient chunks, or contradictory chunks for the confirmed scientific name and requested aspects
- **THEN** the normal assistant chat-time path attempts trusted web search before final answer generation
- **AND** it does not call Trefle, Perenual or `plant_data_lookup` as an intermediate fallback

#### Scenario: Structured providers remain available outside chat-time path

- **WHEN** a non-chat-time backend flow or future offline ingestion flow explicitly uses structured plant-data providers
- **THEN** Trefle and Perenual services may still be called according to their provider contracts

### Requirement: Fetched trusted content ingestion

The system SHALL NOT persist fetched trusted page content in full by default from the assistant chat-time fallback path. When final combined judging validates source-supported claims from fetched content, the system SHALL persist small contextualized claim documents derived from those claims instead of the full page body.

#### Scenario: Fetched content supports validated claim

- **WHEN** trusted fallback page content is successfully fetched and extracted
- **AND** final combined judging returns source support for a claim from that content
- **THEN** the system builds a small validated claim document containing taxonomy, topic, covered aspects, claim, evidence quote, source URL, validation confidence and retrieval timestamp
- **AND** persists the claim document through the existing knowledge/vector-index path

#### Scenario: Full fetched page is not persisted by default

- **WHEN** trusted fallback page content is available during assistant chat-time fallback
- **THEN** the system does not persist the full page body by default

#### Scenario: Persistence failure does not block fallback answer

- **WHEN** validated claim content is available but knowledge persistence or embedding fails
- **THEN** the system still returns the assistant answer using available evidence
- **AND** logs or reports the persistence failure as a non-blocking limitation

### Requirement: Assistant fallback web evidence persistence

The system SHALL persist assistant fallback web evidence through the existing knowledge ingestion path only when the final combined judge returns source-supported claims for at least one requested care aspect and the final status is `full` or safe `partial`. Trusted-domain fallback evidence SHALL retain trusted provenance, while selected external fallback evidence SHALL be persisted only when source support is clear and metadata marks its external fallback status. Each validated source-supported claim SHALL be persisted as a small contextualized knowledge document with covered aspects and validation confidence.

#### Scenario: Trusted fallback claim is ingested

- **WHEN** the assistant answers a botanical question from trusted web-search results because RAG evidence was not full
- **AND** final combined judging returns source support for trusted-source claims
- **THEN** the system builds validated claim documents from source-supported claims and source metadata, marks each document `auto_ingested`, and ingests each document through the LlamaIndex-backed knowledge vector index
- **AND** each source validation status remains trusted

#### Scenario: External fallback claim is ingested conservatively

- **WHEN** the assistant answers a botanical question from one selected external fallback web result because RAG evidence was not full and no allowed-domain search results were returned
- **AND** final combined judging returns clear source support for one or more claims
- **THEN** the system builds validated claim documents from those source-supported claims and source metadata
- **AND** each document is marked `auto_ingested`
- **AND** each document confidence is lower than trusted-domain web evidence confidence
- **AND** the source validation status is `external_fallback`

#### Scenario: Fallback claim is embedded and indexed

- **WHEN** fallback web claim ingestion succeeds for final-judge-supported source claims
- **THEN** the system chunks, embeds, persists and indexes those claims using the configured embedding provider so future retrieval can find them

#### Scenario: Fallback evidence persistence is best effort

- **WHEN** fallback evidence ingestion, embedding or indexing fails after usable web evidence was found
- **THEN** the system does not block the assistant answer and records or logs the persistence limitation for observability

#### Scenario: Off-aspect fallback evidence is not persisted

- **WHEN** assistant fallback web search returns a source that does not appear in final judge `source_support` for any requested aspect
- **THEN** the system does not persist, chunk, embed or vector-index that source

#### Scenario: Source-specific aspects are persisted

- **WHEN** multiple fallback web source-supported claims validate for different requested aspects
- **THEN** the system persists each validated claim with metadata for only that claim's covered aspects
- **AND** each document metadata includes that claim's validation confidence

#### Scenario: Overall web validation confidence remains conservative

- **WHEN** multiple source-supported claims are used for one fallback answer
- **THEN** the answer's overall web validation confidence does not exceed the minimum validation confidence among the included source-supported claims unless a stricter aggregation policy is implemented

### Requirement: Acquisition degradation

The system MUST NOT block the user experience completely when trusted acquisition, trusted page fetching, background validated-claim ingestion, or LlamaIndex pgvector retrieval fails. Normal assistant chat-time plant-care fallback SHALL proceed from non-full RAG to trusted web search without requiring structured plant-data lookup.

#### Scenario: Structured plant-data lookup is skipped in chat-time flow

- **WHEN** RAG evidence is unavailable, partial, insufficient, or contradictory in the normal assistant chat-time plant-care answer path
- **THEN** the system continues to trusted web search/page-fetch fallback before returning a transparent partial, insufficient, contradictory, or conservative response

#### Scenario: Trusted acquisition fails

- **WHEN** no trusted source is found or web evidence cannot be validated after non-full RAG evidence
- **THEN** the system returns the best available partial, insufficient, contradictory, or conservative result with limitations and a retry or manual search path where appropriate

#### Scenario: Trusted page fetch fails

- **WHEN** a trusted source search result is available but page fetching fails because of network, redirect, content type, size, extraction or implementation errors
- **THEN** the system keeps responding with degraded trusted snippet evidence when the final combined judge can validate it instead of blocking the assistant response

#### Scenario: LlamaIndex retrieval fails

- **WHEN** the LlamaIndex pgvector retriever cannot query evidence
- **THEN** the system attempts eligible trusted web search and then returns a degraded result with a limitation notice and retry or manual search path instead of silently using SQL-only vector retrieval as the successful path

#### Scenario: Background claim ingestion fails

- **WHEN** post-response validated claim ingestion, embedding or vector indexing fails
- **THEN** the background task rolls back its own transaction and logs the failure
- **AND** the user-facing assistant answer remains returned

## ADDED Requirements

### Requirement: Combined final evidence judging

The system SHALL run one final combined judge over available RAG evidence and selected web evidence before synthesizing a final answer when RAG evidence is not full.

#### Scenario: Final judge receives combined evidence package

- **WHEN** trusted web search runs because RAG evidence is not full
- **THEN** the final judge receives the user question, confirmed taxonomy, topic, required aspects, RAG chunks, RAG judge result, selected web evidence, source URLs and source metadata

#### Scenario: Final judge may supersede RAG status

- **WHEN** final combined judging evaluates RAG and web evidence together
- **THEN** it may return `full`, `partial`, `insufficient`, or `contradictory` regardless of the earlier RAG-only status

#### Scenario: Final judge outputs source support

- **WHEN** final combined judging marks any aspect covered
- **THEN** it returns source-supported claims with source URLs, covered aspects, evidence quotes and confidence values

#### Scenario: Final judge outputs contradictions

- **WHEN** final combined judging detects conflicting source-supported claims
- **THEN** it returns contradiction entries with aspect, conflicting claims, source URLs, explanation and severity
