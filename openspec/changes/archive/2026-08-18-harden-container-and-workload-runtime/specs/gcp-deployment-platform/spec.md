## ADDED Requirements

### Requirement: Kubernetes workload security baseline

GCP application workloads SHALL enforce the image runtime contract with Kubernetes pod and container security contexts. Application containers MUST run as non-root, MUST disallow privilege escalation, MUST drop all Linux capabilities unless a specific capability is documented as required, and SHALL use `RuntimeDefault` seccomp unless a workload-specific exception documents the concrete runtime reason and compensating control.

#### Scenario: Application workload is rendered

- **WHEN** backend API, frontend, worker, or migration manifests are rendered for an environment
- **THEN** pod or container fields enforce non-root execution and `RuntimeDefault` seccomp
- **AND** each application container disables privilege escalation and drops `ALL` Linux capabilities

#### Scenario: Image metadata regresses to root

- **WHEN** an application image defaults to UID 0 but its workload requires non-root execution
- **THEN** the workload does not silently start as root
- **AND** deployment verification reports the runtime identity failure

#### Scenario: Supporting container requires an exception

- **WHEN** an init container or sidecar cannot satisfy an applicable security-context field
- **THEN** its manifest or adjacent operational documentation identifies the exact container, unsupported field, concrete workload reason, and compensating control
- **AND** omission of the field without that exception is not accepted

### Requirement: Read-only workload filesystems

Application containers SHALL use read-only root filesystems where their verified runtime behavior permits it, and required runtime writes SHALL use explicit minimally scoped volume mounts. Any writable-root exception MUST identify the workload, required operation, and path that prevents read-only operation.

#### Scenario: Workload requires temporary writable storage

- **WHEN** a verified API, frontend, worker, or migration operation requires temporary filesystem writes
- **THEN** the workload mounts an explicit writable volume at the documented path
- **AND** unrelated root filesystem paths remain read-only

#### Scenario: Workload keeps a writable root filesystem

- **WHEN** an application container cannot use a read-only root filesystem
- **THEN** the reviewed deployment artifacts document the failing operation and required writable path instead of silently omitting `readOnlyRootFilesystem`

### Requirement: Explicit container resource governance

Every deployed regular container, init container, and native sidecar SHALL declare CPU and memory requests and limits. Values SHALL be explicit and reviewable for each environment and workload role, including backend API, frontend, migration, worker, Cloud SQL proxy, and any other supporting container.

#### Scenario: Environment manifests declare bounded resources

- **WHEN** Kubernetes manifests are rendered for development or production
- **THEN** every container class has non-empty CPU and memory requests and limits
- **AND** the effective values are visible in the rendered environment artifacts

#### Scenario: Workload roles need different resource profiles

- **WHEN** API, frontend, worker, migration, or sidecar resource needs differ
- **THEN** environment configuration provides explicit role-specific values rather than leaving a role unbounded or applying an undocumented implicit default

#### Scenario: Resource values are operationally tuned

- **WHEN** observed throttling, OOM termination, steady-state usage, or scheduling pressure shows that a resource value is unsuitable
- **THEN** operators update the explicit environment value through review and retain requests and limits for the affected container

### Requirement: Hardened workload rollout and rollback

Deployment operations SHALL verify hardened API, frontend, worker, migration, and supporting-container behavior in development before promotion. Rollback SHALL use a prior reviewed immutable image and compatible manifests without permanently removing the non-root runtime or resource-governance baseline.

#### Scenario: Hardened release is promoted

- **WHEN** a release candidate passes image checks, rendered-manifest policy checks, and development-cluster smoke tests
- **THEN** the same immutable images and reviewed manifest policy structure are eligible for promotion

#### Scenario: Hardened release requires rollback

- **WHEN** runtime filesystem compatibility or resource values cause a deployment failure
- **THEN** operators can redeploy a prior reviewed immutable image and compatible manifest revision
- **AND** any temporary policy exception is explicit and does not leave workloads unbounded or running as root
