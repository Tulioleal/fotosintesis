## ADDED Requirements

### Requirement: Container runtime identity verification

Backend CI SHALL verify the final image's default runtime identity and SHALL execute bounded smoke tests for the production API, worker, and migration commands under that identity.

#### Scenario: Hardened backend image passes CI

- **WHEN** backend CI builds the final runtime image
- **THEN** a deterministic check confirms that its default UID and GID match the documented non-zero runtime identity
- **AND** bounded API, worker, and migration smoke commands complete without a root user override

#### Scenario: Runtime identity or ownership regresses

- **WHEN** the built image defaults to UID 0 or a production command fails because a required path is inaccessible to the runtime user
- **THEN** backend CI fails before image deployment

### Requirement: Rendered workload policy verification

Deployment validation SHALL inspect every rendered environment manifest and SHALL fail when any regular container, init container, or native sidecar lacks required CPU and memory requests or limits. It SHALL also verify the security-context and writable-storage invariants applicable to each application container and SHALL accept an exception only when the exception is explicit, workload-specific, and documents its concrete runtime reason.

#### Scenario: Rendered manifests satisfy the baseline

- **WHEN** deployment manifests are rendered for an environment
- **THEN** policy checks enumerate every regular container, init container, and native sidecar
- **AND** every enumerated container declares CPU and memory requests and limits
- **AND** application containers enforce non-root execution, disabled privilege escalation, dropped Linux capabilities, and `RuntimeDefault` seccomp
- **AND** read-only roots and writable volumes agree with the documented writable-path inventory

#### Scenario: Rendered manifest omits a required field

- **WHEN** a rendered container lacks a required resource or security declaration and has no approved documented exception
- **THEN** deployment validation fails before the manifest is applied

#### Scenario: Standard manifest scanner evaluates the workloads

- **WHEN** Checkov or an equivalent pinned manifest policy scanner runs in CI
- **THEN** findings for root application execution, privilege escalation, required capability drops, seccomp, and missing resource declarations are either resolved or linked to an explicit workload-specific exception

### Requirement: Hardened runtime deployment smoke tests

Development deployment verification SHALL exercise health checks, migrations, background job processing, uploads, and configured provider calls under the hardened workload identity and filesystem policy before the same image and manifest policy structure is promoted.

#### Scenario: Development workload behavior remains functional

- **WHEN** hardened images and rendered manifests are deployed to the development cluster
- **THEN** migrations complete, API and frontend health checks pass, the worker processes a representative job, and representative upload and provider operations succeed

#### Scenario: Resource exhaustion remains bounded

- **WHEN** a development workload reaches its configured CPU or memory limit during a controlled verification
- **THEN** throttling or container termination is confined to the bounded workload
- **AND** Kubernetes can report and recover or restart the workload without unbounded node-wide consumption
