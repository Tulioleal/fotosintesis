## ADDED Requirements

### Requirement: Object storage deletion compensation

The object storage abstraction SHALL expose a best-effort delete operation by object path so that callers can remove a stored object when subsequent durable work fails. Cleanup failures SHALL be logged with the object identifier and SHALL NOT include image content.

#### Scenario: Storage interface exposes delete operation

- **WHEN** a caller has stored an object and later durable work fails
- **THEN** the caller can invoke a delete operation keyed by the stored object path to remove the object on a best-effort basis

#### Scenario: Cleanup failure is logged without content

- **WHEN** a best-effort object deletion fails
- **THEN** the failure is logged with the object path or identifier
- **AND** the log does not include the image bytes or any decoded image content
