## ADDED Requirements

### Requirement: Gemini-backed judge evaluation
The evaluation pipeline SHALL support using the configured Gemini judge provider through the existing judge evaluation interface.

#### Scenario: Evaluation runner uses Gemini judge
- **WHEN** the judge provider is configured as Gemini and an evaluation case requires LLM-as-judge scoring
- **THEN** the evaluation runner scores the case through the configured judge provider and stores score, pass status and failure reasons from the internal judge result

#### Scenario: Gemini judge remains independent from runtime generation
- **WHEN** the judge provider is configured as Gemini and the model provider is configured as mock, OpenAI or another provider
- **THEN** evaluation judging uses Gemini without changing the provider used for runtime assistant generation
