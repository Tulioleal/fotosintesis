## MODIFIED Requirements
### Requirement: Chat experience

The system SHALL provide a chat API and frontend conversation UI for a plant-care assistant. The blocking JSON chat contract SHALL remain canonical; the system MAY additionally expose a server-sent-events variant of the same conversation flow that streams bounded stage-progress events and terminates with the identical response payload, subject to the streaming capability contract.

#### Scenario: Blocking contract is unaffected by streaming

- WHEN a client uses the blocking chat endpoint
- THEN request validation, persistence, retryable-failure semantics, and the response schema are identical to the pre-streaming contract
- AND stage emission adds no observable difference to the blocking response

#### Scenario: Both transports share one execution path

- WHEN a chat turn executes via either transport
- THEN the same assistant service and graph orchestration produce the outcome
- AND streaming differs only in transport framing, not in routing, validation, or persistence behavior
