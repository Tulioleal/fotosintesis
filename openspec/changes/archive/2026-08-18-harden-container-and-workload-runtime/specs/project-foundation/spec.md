## ADDED Requirements

### Requirement: Unprivileged backend runtime identity

The final backend image SHALL define a dedicated runtime user and group with fixed non-zero numeric IDs, SHALL use that user as its default runtime identity, and SHALL grant it no ownership beyond the application files and writable paths required at runtime. Build steps MAY execute as root, but the shipped API, worker, and migration processes MUST NOT execute as UID 0.

#### Scenario: Built backend image has a non-root default user

- **WHEN** the final backend image is inspected or started without a user override
- **THEN** its runtime process reports the documented non-zero UID and GID
- **AND** the image does not default to UID 0

#### Scenario: Shared backend commands use the runtime identity

- **WHEN** the production API, worker, and migration commands execute from the final backend image
- **THEN** each command starts and performs its required initialization under the same documented unprivileged identity

### Requirement: Minimal explicit runtime writes

The backend runtime SHALL avoid writes to the image root filesystem except for documented required paths, and each required writable path SHALL be narrowly scoped through image ownership or runtime-mounted storage appropriate to its data lifetime.

#### Scenario: Runtime writable paths are inventoried

- **WHEN** API, worker, and migration commands are tested from the final backend image
- **THEN** cache, home, upload-staging, and temporary-file writes are either disabled, redirected to documented writable paths, or shown not to occur
- **AND** broad ownership of unrelated image or system directories is not required

#### Scenario: Runtime command encounters an undeclared write

- **WHEN** an API, worker, or migration operation attempts to write outside its documented writable paths
- **THEN** image or workload verification fails until the write is removed or an explicit minimal writable path is reviewed
