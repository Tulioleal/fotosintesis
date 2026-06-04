## MODIFIED Requirements

### Requirement: RAG-grounded answers
The assistant MUST use retrieved or fallback evidence for botanical answers when available and SHALL synthesize final botanical responses with the configured language model. The synthesized response MUST be grounded only in supplied evidence, SHALL communicate uncertainty when evidence is limited, incomplete or degraded, and MUST preserve source attribution in the assistant API response. If model generation fails, the assistant SHALL return a deterministic evidence summary and record the model failure as a non-blocking tool failure.

#### Scenario: Evidence-backed answer
- **WHEN** relevant documents are retrieved for a botanical question
- **THEN** the assistant generates the final response with the configured model using those documents and avoids unsupported claims

#### Scenario: Structured evidence-backed answer
- **WHEN** RAG evidence is insufficient and structured plant-data evidence is sufficient for a botanical question
- **THEN** the assistant generates the final response with the configured model using the structured evidence and provider metadata

#### Scenario: Trusted web evidence-backed answer
- **WHEN** RAG and structured plant-data evidence are insufficient and trusted web evidence is available
- **THEN** the assistant generates the final response with the configured model using trusted web evidence and source metadata

#### Scenario: Model synthesis fails
- **WHEN** model generation fails while evidence is available for a botanical answer
- **THEN** the assistant returns a deterministic summary from the available evidence and records the model failure without dropping source attribution
