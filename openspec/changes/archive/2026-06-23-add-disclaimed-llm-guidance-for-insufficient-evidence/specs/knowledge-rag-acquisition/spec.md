## ADDED Requirements

### Requirement: Runtime-only guidance is excluded from knowledge acquisition
The system SHALL treat `general_guidance_with_disclaimer` content as runtime-only model output. The system MUST NOT persist, chunk, embed, index, cite, or emit ingestion candidates for model-generated general guidance unless each emitted claim is independently present in final normalized judge `source_support` as a validated source-supported claim.

#### Scenario: Insufficient disclaimed answer emits no ingestion claims
- **WHEN** final answer generation uses `general_guidance_with_disclaimer` after answerability validation returns `status: "insufficient"`
- **THEN** the assistant emits no ingestion claim payloads for the generated general guidance
- **AND** the knowledge acquisition path does not persist, chunk, embed, or index the generated general guidance

#### Scenario: Partial answer persists only validated source support
- **WHEN** final answer generation includes both validated source-supported facts and disclaimed general guidance for missing non-safety aspects
- **THEN** ingestion claim payloads, if any, are derived only from final normalized judge `source_support`
- **AND** each payload includes only the source-supported claim, source quote, source URL, and covered aspects from that validated source support
- **AND** no sentence or claim from the general-guidance section is included in `source_support` or ingestion payloads

#### Scenario: General guidance is never cited as evidence
- **WHEN** the assistant returns disclaimed general guidance
- **THEN** citations and assistant source metadata apply only to validated retrieved or web evidence
- **AND** the final answer does not imply that retrieved sources validated the general-guidance section

#### Scenario: Final assistant prose is not persisted as knowledge
- **WHEN** the assistant returns a disclaimed guidance answer to the user
- **THEN** the knowledge acquisition path does not persist the final assistant response text as a knowledge document
