## ADDED Requirements

### Requirement: Evaluation executes the current assistant orchestration

The evaluation runner SHALL execute the current assistant orchestration (the LangGraph `AssistantGraph`) for every run case, and SHALL derive the observed result from the graph state rather than from a reference or a fabricated trace.

#### Scenario: Case runs through the assistant graph

- **WHEN** the evaluation runner evaluates a case in recorded or live mode
- **THEN** the runner invokes the current assistant graph with the case input and setup state
- **AND** the observed response, retrieval evidence, tool outcomes, and validation state are read from the resulting graph state

#### Scenario: Reference mode cannot produce a passing run

- **WHEN** the evaluation runner runs in reference mode
- **THEN** the run is marked non-passing regardless of any computed scores
- **AND** reference text is never reported as graph-produced candidate text

### Requirement: Observed output is not derived from references

Observed candidate text, retrieval records, and tool traces SHALL NOT be populated from `reference_output` or from expected retrieval or tool fixtures. Expected tool behavior SHALL be expressed as assertions, and expected retrieval SHALL identify relevant documents or aspects without fixing order.

#### Scenario: Case does not carry fabricated traces

- **WHEN** a dataset case declares expected tool behavior or expected relevant documents
- **THEN** the case stores them as assertions or relevance identifiers
- **AND** the runner does not copy those fields into the observed result

#### Scenario: Candidate text comes from graph production

- **WHEN** the graph produces a response for a case
- **THEN** the observed candidate text equals the graph-produced answer
- **AND** `reference_output` is used only as a scoring reference, never as the candidate

### Requirement: Deterministic recorded execution mode

The evaluation runner SHALL support a recorded mode that replays versioned provider recordings at the existing provider interfaces. The assistant graph, repositories, retrieval, routing, and persistence SHALL still execute during replay.

#### Scenario: Recorded run is reproducible

- **WHEN** the same recorded set is replayed against the same dataset and code
- **THEN** repeated runs produce the same observed results and scores

#### Scenario: Recordings operate at provider boundaries

- **WHEN** a recorded run executes the graph
- **THEN** only provider responses are replayed
- **AND** graph routing, repository behavior, and validation still execute normally

### Requirement: Recording integrity is enforced

Recordings SHALL be versioned against the provider contract, SHALL record provider identity, and SHALL be rejected explicitly when missing, stale, or incompatible.

#### Scenario: Missing recording fails explicitly

- **WHEN** a recorded run encounters a provider call with no matching recording entry
- **THEN** the runner raises an explicit evaluation infrastructure error
- **AND** the case is classified as an execution error rather than a quality failure

#### Scenario: Incompatible recording fails explicitly

- **WHEN** a recording's schema version or provider identity does not match the current provider contract
- **THEN** the runner rejects the recording with an explicit mismatch error instead of replaying it

### Requirement: Captured results are bounded

Each captured result SHALL record the actual response and answer language, selected taxonomy, classified topic, and required aspects when available, retrieved evidence identifiers and source metadata, judge status, and tool name, success state, and bounded error category. Sensitive prompts, source bodies, user notes, and credentials SHALL NOT be reported.

#### Scenario: Result captures bounded observed fields

- **WHEN** a case completes with an observed graph state
- **THEN** the captured result includes the actual answer, answer language, taxonomy, topic, required aspects, retrieved evidence identifiers, source metadata, judge status, and bounded tool outcomes
- **AND** the captured result excludes prompts, raw model reasoning, source bodies, user notes, and credentials

#### Scenario: Tool outcome is captured without sensitive input

- **WHEN** a tool is invoked during an evaluated run
- **THEN** the captured record includes the tool name, success state, and a bounded error category
- **AND** the captured record excludes tool arguments, retrieved document bodies, and provider internals

### Requirement: Opt-in live execution mode

The evaluation runner SHALL support a live mode that calls configured providers and records cost, variability, and failure metadata. Live mode SHALL be opt-in, clearly marked non-deterministic, and excluded from CI.

#### Scenario: Live mode records operational metadata

- **WHEN** the runner evaluates in live mode
- **THEN** the run records provider identity, latency, and bounded usage metadata
- **AND** the report marks the run as non-deterministic

#### Scenario: Live mode is not the CI default

- **WHEN** the evaluation runner is invoked for CI without an explicit mode
- **THEN** the runner uses recorded mode
- **AND** live mode requires an explicit opt-in

### Requirement: Execution outcomes are classified

Reports and result files SHALL distinguish execution errors, metric errors, and quality failures, and SHALL NOT collapse a failed execution into a low-quality successful execution.

#### Scenario: Failed execution is separate from quality failure

- **WHEN** a case fails because the graph raised an error or a provider recording was missing
- **THEN** the case status is an execution or metric error
- **AND** the failure is reported separately from cases that ran successfully but scored below thresholds

#### Scenario: Report states mode and recording version

- **WHEN** an evaluation report is generated
- **THEN** the report includes the execution mode, the recording version when applicable, and the applied threshold profile

### Requirement: Unsupported cases are reconciled

Evaluation cases whose expected tools or flows are absent from the current graph SHALL be corrected or marked explicitly, and SHALL NOT be scored as if their expected behavior had occurred.

#### Scenario: Case references an absent tool

- **WHEN** a dataset case declares an expected tool that the current graph does not expose
- **THEN** the runner marks the case unsupported with an explicit reason
- **AND** the case is not scored as a passing or failing quality result
