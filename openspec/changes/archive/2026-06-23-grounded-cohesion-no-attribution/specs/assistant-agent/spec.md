## MODIFIED Requirements

### Requirement: Aspect-gated care answer synthesis

The assistant SHALL validate local and web evidence against the requested domain-qualified `required_aspects` before synthesizing a plant-care answer. Final care answers MUST distinguish source-validated claims from unsupported or general guidance, SHALL preserve the classified `answer_language`, and MUST integrate source-backed claims and any complementary general guidance in a continuous narrative that signals the origin of each part through soft linguistic connectors. Validation SHALL use context-aware thresholds based on aspect safety sensitivity and structural strength of the normalized judge result. The normalized judge result MUST use only canonical requested aspect identifiers in `covered_aspects` and `missing_aspects`; explanatory judge text MUST remain in reason fields and MUST NOT be used as a missing aspect. Diagnosis answers MUST present causes as hypotheses unless source-supported evidence directly supports a definitive claim. Final prose MUST NOT include URLs, institution names, or blocks labeled `Source-backed`, `Sources`, `References`, or equivalents; source attribution is delivered through the structured `sources[]` response field, not through the prose. The `_grounded_answer_prompt` MUST NOT instruct the model to add an attribution block, source link, or institutional name based on `evidence_type` (including `evidence_type == "structured_api"`).

#### Scenario: Complete aspect coverage answers directly

- **WHEN** validated evidence covers every requested required aspect above the configured threshold
- **THEN** the assistant answers directly in `answer_language` using the validated evidence and source metadata without mentioning internal validation steps
- **AND** the response prose contains no URLs, institution names, or `Source-backed` / `Sources` / `References` blocks
- **AND** source metadata is delivered only through the structured `sources[]` field

#### Scenario: Complete partial judge coverage normalizes to full

- **WHEN** the answerability judge returns `status: "partial"` with valid source support for every requested required aspect
- **AND** the normalized covered aspects include every requested required aspect
- **AND** the result has no source-supported contradictions
- **THEN** the assistant treats the normalized result as `status: "full"` and `answerable: true`
- **AND** the assistant records no missing aspects for that answerability result

#### Scenario: Strong full-support non-safety answer accepted with lower threshold

- **WHEN** the answerability judge returns `status: "full"`, `answerable: true`, all requested aspects are covered, `source_support` is non-empty, `contradictions` is empty, and no requested aspect is safety-sensitive
- **AND** the judge confidence is above `assistant_strong_answer_validation_threshold` (default 0.30)
- **THEN** the assistant treats the evidence as sufficient and answers from RAG without triggering web fallback

#### Scenario: Safety-sensitive aspect requires strict threshold

- **WHEN** a requested aspect is a `toxicity_*` or `safety_*` aspect that affects pet, child, human, ingestion, skin-irritation, chemical-treatment, disposal, cross-contamination, vet, or poison-control guidance
- **THEN** validation requires the aspect confidence to be above `assistant_safety_validation_threshold` (default 0.85) before marking the aspect covered

#### Scenario: Partial non-critical coverage answers covered aspects

- **WHEN** validated evidence covers at least one requested non-critical required aspect but leaves other non-critical aspects missing
- **THEN** the assistant answers the source-supported parts in continuous prose
- **AND** briefly states which requested aspects could not be source-validated
- **AND** any conservative general guidance for missing aspects is introduced with a soft linguistic connector (for example, `As a general guideline…`, `In general terms…`, `A common complementary practice is…`, `As a complementary reference…`) and is treated as general and not source-validated for the specific plant/question
- **AND** the response prose contains no URLs, institution names, or `Source-backed` / `Sources` / `References` blocks

#### Scenario: True partial coverage remains partial

- **WHEN** the answerability judge returns source-supported coverage for some but not all requested non-critical required aspects
- **THEN** the assistant preserves `status: "partial"` and `answerable: false`
- **AND** the assistant computes missing aspects from requested aspects that are not covered after normalization

#### Scenario: Diagnosis remains hypothetical

- **WHEN** requested aspects include `diagnosis_*` causes and evidence supports multiple possible causes
- **THEN** the assistant presents causes as hypotheses or possibilities
- **AND** the assistant does not state a definitive diagnosis unless source-supported evidence directly identifies the cause for the specific plant and symptom context

#### Scenario: No validated coverage returns transparent insufficient answer

- **WHEN** no requested required aspects are covered by validated evidence
- **THEN** the assistant states that source-backed evidence was insufficient for the specific plant/question
- **AND** any conservative general guidance is introduced with a soft linguistic connector and is treated as general and not source-validated for the specific plant/question
- **AND** the assistant does not cite general guidance as source-backed evidence
- **AND** the response prose contains no URLs, institution names, or `Source-backed` / `Sources` / `References` blocks

#### Scenario: Safety-sensitive missing evidence returns conservative guidance

- **WHEN** a safety-sensitive care question lacks direct validated evidence for the primary safety aspect at the configured safety-sensitive threshold
- **THEN** the assistant states that direct source-backed evidence was unavailable for the specific plant/question
- **AND** the assistant may provide conservative safety guidance introduced with a soft linguistic connector and treated as general and not source-validated
- **AND** the assistant does not claim the plant is safe, toxic, edible, or consumable without direct evidence
- **AND** the response prose contains no URLs, institution names, or `Source-backed` / `Sources` / `References` blocks

#### Scenario: Contradictory evidence is presented without definitive claim

- **WHEN** final evidence validation reports contradictory source-supported claims for a requested aspect
- **THEN** the assistant states in generic terms that the consulted sources conflict (for example, "there is contradictory information among the consulted sources about X") without naming or linking specific sources
- **AND** the response prose contains no URLs, institution names, or `Source-backed` / `Sources` / `References` blocks
- **AND** the assistant avoids a definitive recommendation from the contradictory evidence
- **AND** source metadata continues to be delivered only through the structured `sources[]` field

### Requirement: RAG-grounded answers

The assistant MUST use retrieved or fallback evidence for botanical answers when available and SHALL synthesize final botanical responses with the configured language model. The synthesized response MUST be grounded in supplied source-supported evidence for verified claims, SHALL communicate uncertainty proportionally when evidence is limited, incomplete or contradictory, and MUST NOT include URLs, institution names, or `Source-backed` / `Sources` / `References` blocks in the user-facing prose. Source attribution MUST be preserved in the assistant API response through the structured `sources[]` field rather than through the prose. The `_grounded_answer_prompt` MUST instruct the model to integrate source-backed claims and any complementary general guidance into continuous narrative prose and to signal general-guidance content with soft linguistic connectors. The prompt MUST NOT inject an attribution instruction that depends on `evidence_type`. RAG evidence SHALL be considered full only when answerability evaluation determines that it directly answers every requested required aspect. When RAG is structurally strong and meets the strong-answer threshold, the assistant SHALL NOT trigger web fallback. When persisted retrieval is not full and trusted live web fallback evidence is available, the assistant MUST prefer fetched trusted page content over citation-only snippets while still answering from trusted snippets when page fetching fails. If grounded model generation fails, the assistant SHALL either perform one allowed model-based recovery generation from the same structured evidence and `answer_language` or return a retryable machine-readable failure when no model-generated response can be produced.

#### Scenario: Strong RAG answer accepted without web fallback

- **WHEN** RAG evidence is structurally strong (status full, answerable, all aspects covered, source support present, no contradictions) and confidence is above `assistant_strong_answer_validation_threshold`
- **AND** no requested aspect is safety-sensitive
- **THEN** the assistant answers from RAG evidence without calling trusted web search
- **AND** the response metadata does not include `web_search_used` in fallback reasons
- **AND** the response prose contains no URLs, institution names, or `Source-backed` / `Sources` / `References` blocks

#### Scenario: Evidence-backed answer

- **WHEN** relevant documents are retrieved for a botanical question
- **AND** strict answerability evaluation determines those documents fully answer the user question
- **THEN** the assistant generates the final response with the configured model using those documents and avoids unsupported claims
- **AND** the response prose contains no URLs, institution names, or `Source-backed` / `Sources` / `References` blocks
- **AND** source metadata is delivered only through the structured `sources[]` field

#### Scenario: Retrieved evidence not full

- **WHEN** relevant documents are retrieved for a botanical question
- **AND** answerability evaluation determines those documents are `partial`, `insufficient`, or `contradictory`
- **THEN** the assistant does not generate a RAG-only final answer from those documents
- **AND** records an internal RAG answerability status for routing and diagnostics

#### Scenario: Trusted web evidence-backed answer

- **WHEN** RAG evidence is not full and trusted web evidence is available
- **THEN** the assistant runs a final combined judge over RAG and web evidence
- **AND** generates the final response with the configured model using only final-judge-supported source claims for verified statements
- **AND** records an internal `web_search_used` fallback reason
- **AND** the response prose contains no URLs, institution names, or `Source-backed` / `Sources` / `References` blocks

#### Scenario: Fetched trusted page content used for fallback answer

- **WHEN** persisted retrieval is not full and trusted live web fallback returns extracted page content
- **THEN** the assistant answer uses the extracted trusted page content when the final combined judge supports claims from that content
- **AND** the assistant does not rely only on original citation or snippet markdown for those supported claims
- **AND** the response prose contains no URLs, institution names, or `Source-backed` / `Sources` / `References` blocks

#### Scenario: Trusted snippet used when page fetch fails

- **WHEN** persisted retrieval is not full and trusted web fallback has a trusted search result whose page fetch fails
- **THEN** the assistant may answer using the trusted snippet if the final combined judge validates the snippet for a requested aspect
- **AND** no fetch exception blocks the response
- **AND** the response prose contains no URLs, institution names, or `Source-backed` / `Sources` / `References` blocks

#### Scenario: Safety question lacks direct evidence

- **WHEN** the user asks a pet safety, edibility, toxicity or consumption question
- **AND** final combined judging does not provide direct source-supported evidence for the safety aspect
- **THEN** the assistant returns conservative safety guidance introduced with a soft linguistic connector and treated as general and not source-validated for the specific plant/question
- **AND** recommends not consuming the plant for edibility or consumption questions
- **AND** recommends keeping the plant away from pets and consulting veterinary or poison-control style help if ingestion occurs for pet safety or toxicity questions
- **AND** records an internal `conservative_safety_fallback` fallback reason
- **AND** the response prose contains no URLs, institution names, or `Source-backed` / `Sources` / `References` blocks

#### Scenario: Contradictory trusted evidence

- **WHEN** final combined judging reports contradictory source-supported evidence
- **THEN** the assistant describes the conflict in generic terms (for example, "there is contradictory information among the consulted sources about X") without naming or linking specific sources
- **AND** the response prose contains no URLs, institution names, or `Source-backed` / `Sources` / `References` blocks
- **AND** does not choose one claim as definitive unless the final judge resolves the contradiction as full or partial with clear support
- **AND** source metadata continues to be delivered only through the structured `sources[]` field

#### Scenario: Model synthesis fails with recoverable output failure

- **WHEN** grounded model generation fails while evidence is available for a botanical answer
- **AND** the failure category is compatible with recovery, such as empty output, invalid output or prompt-specific output failure
- **THEN** the assistant builds a structured recovery generation payload using only supplied evidence facts, source support, limitations and `answer_language`
- **AND** attempts at most one model-based recovery generation
- **AND** records the model failure without dropping source attribution metadata from the structured response

#### Scenario: Model synthesis fails because all providers are unavailable

- **WHEN** grounded model generation fails while evidence is available
- **AND** no configured model provider can produce a model-generated recovery response
- **THEN** the assistant returns a retryable machine-readable error instead of fallback prose
- **AND** the response does not include raw evidence as user-facing assistant content
- **AND** no assistant message is persisted for the failed turn
