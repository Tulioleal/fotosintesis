## ADDED Requirements

### Requirement: Fetched fallback evidence context
The assistant SHALL include fetched trusted page content in fallback answer evidence context when that content is available.

#### Scenario: Fetched content supports fallback answer
- **WHEN** existing RAG evidence is insufficient and fallback web search yields trusted results with successfully extracted page content
- **THEN** the assistant generates its fallback answer using the extracted page content rather than only search snippets
- **AND** cites the corresponding trusted source URLs in the response sources

#### Scenario: Fallback answer degrades to snippets
- **WHEN** fallback web search yields trusted results but page fetch or extraction fails
- **THEN** the assistant generates its fallback answer from the trusted result snippets
- **AND** does not claim that full page content was acquired
