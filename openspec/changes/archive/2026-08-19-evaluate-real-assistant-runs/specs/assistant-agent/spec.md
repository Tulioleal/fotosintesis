## ADDED Requirements

### Requirement: Bounded evaluation traces

The assistant SHALL expose bounded, redacted traces of tool outcomes and retrieved evidence identifiers needed by evaluation harnesses. These traces MUST exclude prompts, source bodies, raw model reasoning, user notes, and credentials.

#### Scenario: Tool outcome trace is bounded

- **WHEN** the assistant executes a tool during a chat turn
- **THEN** the graph state includes a bounded tool record with the tool name, success state, and a bounded error category
- **AND** the record excludes tool arguments, retrieved document bodies, and provider internals

#### Scenario: Retrieval evidence identifiers are exposed

- **WHEN** the assistant retrieves evidence during a chat turn
- **THEN** the graph state exposes the retrieved evidence identifiers and bounded source metadata
- **AND** the state does not expose full evidence text, prompts, or user notes

#### Scenario: Traces are available to the evaluation harness

- **WHEN** the evaluation harness runs the assistant graph
- **THEN** it can read the bounded tool and retrieval traces from the returned graph state without additional provider or database calls
