## Purpose

Define the offline evaluation pipeline for measuring MVP AI flows across retrieval, generation, judge quality, tool behavior, visual identification and reporting.
## Requirements
### Requirement: Evaluation dataset and runner

The system SHALL include an evaluation dataset format, an initial 50-case seed and a runner for target MVP flows. Run approval SHALL define its aggregate pass-rate denominator as the supported cases only. Each evaluation profile SHALL configure a minimum supported-case ratio, and a run whose supported share falls below that ratio SHALL fail as a coverage failure independent of scores.

#### Scenario: Pass rate uses supported cases as denominator

- **WHEN** a run completes with passing cases, failing cases, and unsupported cases
- **THEN** the aggregate pass rate divides passing supported cases by total supported cases
- **AND** unsupported cases appear only as reconciled exclusions with reasons

#### Scenario: Dataset shrinkage fails the run

- **WHEN** the supported-case ratio falls below the profile's configured minimum
- **THEN** the run fails with an explicit coverage failure naming the ratio and the unsupported reasons
- **AND** no approval verdict based on scores is emitted

### Requirement: Retrieval and generation metrics

The system SHALL calculate retrieval_recall@5, precision@5, BERTScore and ROUGE-L where applicable.

#### Scenario: Text case evaluated

- **WHEN** a case includes retrieved documents and reference text
- **THEN** the system calculates retrieval and generation metrics and stores the scores

### Requirement: Judge rubric

The system SHALL evaluate grounding, botanical correctness, usefulness, clarity, safety, uncertainty handling and tool use with an LLM-as-a-judge rubric.

#### Scenario: Judge fails case

- **WHEN** a response fails grounding, safety or botanical correctness criteria
- **THEN** the system marks the case as failed and stores the failure reason

### Requirement: Agent and visual metrics

The system SHALL calculate tool_success_rate, unnecessary_web_search_rate, failed_action_claim_rate and visual identification metrics.

#### Scenario: Tool failure claimed as success

- **WHEN** a failed tool action is claimed as completed in a response
- **THEN** the system records a failed_action_claim_rate violation

### Requirement: Evaluation report

The system SHALL persist runs, scores, failures and per-flow summaries and generate a final evaluation report. Each executed run SHALL retain its report and machine-readable results as versioned artifacts under a runs directory.

#### Scenario: Run artifacts are retained

- **WHEN** a run completes in any mode
- **THEN** the runner writes `report.md` and a machine-readable result file for that run id under the runs directory
- **AND** retention of historical run directories is bounded by configured policy

### Requirement: Gemini-backed judge evaluation

The evaluation pipeline SHALL support using the configured Gemini judge provider through the existing judge evaluation interface.

#### Scenario: Evaluation runner uses Gemini judge

- **WHEN** the judge provider is configured as Gemini and an evaluation case requires LLM-as-judge scoring
- **THEN** the evaluation runner scores the case through the configured judge provider and stores score, pass status and failure reasons from the internal judge result

#### Scenario: Gemini judge remains independent from runtime generation

- **WHEN** the judge provider is configured as Gemini and the model provider is configured as mock, OpenAI or another provider
- **THEN** evaluation judging uses Gemini without changing the provider used for runtime assistant generation

