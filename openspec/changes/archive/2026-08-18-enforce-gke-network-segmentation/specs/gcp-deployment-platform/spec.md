## ADDED Requirements

### Requirement: Cluster network policy enforcement

The GKE cluster SHALL enable a supported network policy enforcement mechanism explicitly in OpenTofu, and application namespaces SHALL apply default-deny ingress and egress baselines with narrow allow rules for required traffic.

#### Scenario: Enforcement is enabled

- **WHEN** the GKE cluster is configured for an environment
- **THEN** OpenTofu explicitly enables a supported enforcement mechanism (such as Dataplane V2)
- **AND** the enforcement choice and any in-place update or recreation requirement are documented

#### Scenario: Application namespace defaults deny traffic

- **WHEN** application manifests are rendered for an environment
- **THEN** the application namespace includes default-deny ingress and egress NetworkPolicies
- **AND** required traffic is represented by explicit narrow allow policies rather than broad exceptions

#### Scenario: External provider egress is documented

- **WHEN** application workloads need access to external model, search, taxonomy, or evidence providers
- **THEN** the policy allows only the bounded egress the chosen mechanism supports (for example, HTTPS egress)
- **AND** documentation states the limitation instead of claiming FQDN-level isolation

#### Scenario: Enforcement must roll back

- **WHEN** a network policy deployment disrupts required traffic
- **THEN** operators can disable enforcement or remove the policy resources to restore previous connectivity
- **AND** the rollback path is documented and exercised before promotion
