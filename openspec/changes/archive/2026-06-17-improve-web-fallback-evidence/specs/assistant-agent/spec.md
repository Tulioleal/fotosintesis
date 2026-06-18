## ADDED Requirements

### Requirement: Web fallback evidence quality

The assistant web fallback SHALL distinguish fetched page content from snippet-only search metadata before answer synthesis. Snippet-only evidence SHALL NOT be treated as strong usable evidence unless it directly covers at least one requested required aspect. The assistant SHALL prefer fetched trusted page content over snippets when constructing combined web evidence for judging and final answer generation.

#### Scenario: Fetched content supports requested aspect
- **WHEN** web fallback fetches trusted page content that directly covers a requested required aspect
- **THEN** the assistant includes that fetched content in the combined evidence passed to the answerability judge
- **AND** the source can support a source-backed answer when the judge returns source support for that aspect

#### Scenario: Snippet-only result lacks direct aspect coverage
- **WHEN** a web search result has no fetched page content
- **AND** its snippet does not directly answer any requested required aspect
- **THEN** the assistant does not treat that result as usable evidence for a source-backed answer
- **AND** the assistant may still log the result as a selected but weak candidate

#### Scenario: Snippet-only result directly covers requested aspect
- **WHEN** a web search result has no fetched page content
- **AND** its snippet directly covers a requested required aspect
- **THEN** the assistant may pass the snippet to the answerability judge as weak web evidence
- **AND** the evidence metadata identifies that the support came from snippet-only evidence

### Requirement: Web fallback confidence is informational

The assistant SHALL NOT reject non-safety web fallback evidence solely because the answerability judge confidence is below the general evidence validation threshold. For web fallback, direct requested-aspect coverage, source support, contradiction handling, and safety-sensitive aspect policy SHALL determine whether evidence can support an answer. Confidence SHALL remain available as diagnostics and metadata.

#### Scenario: Useful web evidence has low confidence
- **WHEN** combined web evidence directly covers all requested non-safety required aspects with source support and no contradictions
- **AND** the judge confidence is below the general evidence validation threshold
- **THEN** the assistant can use the web evidence for a source-backed answer
- **AND** the assistant records the confidence as informational metadata

#### Scenario: Safety-sensitive web evidence remains strict
- **WHEN** the requested aspect is safety-sensitive, including pet toxicity or human edibility
- **THEN** the assistant requires direct evidence and safety-sensitive validation before using web fallback for a definitive source-backed answer

#### Scenario: Web evidence lacks direct support
- **WHEN** web evidence does not directly cover the requested required aspects
- **THEN** the assistant treats the web evidence as insufficient regardless of confidence

### Requirement: Web fallback search reuse

The assistant SHALL avoid duplicate live web searches when usable search candidates or fetched evidence from the current retrieval/acquisition path are already available for the same confirmed taxonomy and requested aspects. Reused candidates MUST still pass trusted-source validation and answerability judging before they can support an answer.

#### Scenario: Acquisition search candidates are reusable
- **WHEN** knowledge acquisition already searched web sources during the same assistant request
- **AND** the candidates match the confirmed taxonomy and requested aspects closely enough for fallback evaluation
- **THEN** assistant web fallback reuses those candidates or their fetched evidence before issuing another search provider call

#### Scenario: Reused candidates fail validation
- **WHEN** reused search candidates do not provide direct aspect coverage after judging
- **THEN** the assistant treats them as insufficient
- **AND** the assistant does not present them as source-backed evidence

#### Scenario: No reusable candidates are available
- **WHEN** the current request has no usable prior search candidates or fetched evidence
- **THEN** assistant web fallback may issue a new trusted web search
