## ADDED Requirements

### Requirement: Network policy verification

Deployment validation SHALL verify that cluster enforcement is effective and that workload NetworkPolicies allow required traffic while denying unexpected traffic.

#### Scenario: Enforcement is proven by probes

- **WHEN** enforcement is enabled in development
- **THEN** an intentionally denied pod-to-pod connection fails
- **AND** an allowed connection succeeds

#### Scenario: Required traffic remains functional

- **WHEN** default-deny policies and allow rules are applied
- **THEN** frontend, backend, worker, migrations, Cloud SQL, DNS, Workload Identity, External Secrets, Managed Prometheus, ingress health checks, and deployment smoke checks pass

#### Scenario: Rendered policies are validated

- **WHEN** NetworkPolicy manifests are rendered for an environment
- **THEN** rendered-manifest validation confirms selectors match deployed workloads and required allow rules are present
- **AND** validation does not treat policy YAML presence alone as proof of enforcement
