## ADDED Requirements

### Requirement: Authentication limiter verification

The system SHALL include automated tests that verify authentication limit response contracts, privacy properties, storage-failure policies, atomic concurrency bounds, and distributed enforcement.

#### Scenario: Backend limiter tests run

- **WHEN** backend unit and PostgreSQL integration tests run
- **THEN** they verify endpoint thresholds, atomic concurrent updates, expiry cleanup, successful-login relaxation, safe storage-failure behavior, and equivalent known-versus-unknown recovery outcomes

#### Scenario: Frontend limiter tests run

- **WHEN** frontend component and authentication journey tests run
- **THEN** they verify `429` and `Retry-After` propagation, bounded retry presentation, disabled resubmission, and neutral recovery copy

#### Scenario: Multi-replica verification runs

- **WHEN** the deployment verification sends matching invalid credential attempts through at least two application instances
- **THEN** their combined allowed attempts do not exceed the configured shared limit

### Requirement: Authentication limiter deployment contract

The Kubernetes deployment SHALL configure documented authentication limit profiles, keyed-digest secrets, trusted proxy behavior, retention, and endpoint-specific storage-failure policies consistently across replicas without committing secret values.

#### Scenario: Deployment artifacts are rendered

- **WHEN** authentication limiter deployment configuration is rendered for an environment
- **THEN** every relevant frontend and backend replica receives compatible non-secret policy settings
- **AND** keyed-digest material is projected from the runtime secret mechanism

#### Scenario: Limiter metrics are scraped

- **WHEN** authentication abuse metrics are emitted by application replicas
- **THEN** existing monitoring discovers the metrics with only closed endpoint-category and outcome labels

### Requirement: Trusted proxy deployment verification

The deployment SHALL document and test the exact GKE ingress-to-frontend trust chain used for source identity and SHALL apply a conservative identity when that chain cannot be established.

#### Scenario: Forwarding header spoofing is tested

- **WHEN** deployment verification sends requests with spoofed forwarding-header entries
- **THEN** the application ignores untrusted entries and does not create attacker-selected limiter identities

### Requirement: Edge protection remains complementary

Any Cloud Armor or equivalent volumetric rate limit SHALL be configured and documented as a separate optional edge control and MUST NOT replace application account-aware authentication limits.

#### Scenario: Edge protection is absent or changed

- **WHEN** no edge rate-limit policy is enabled or its threshold changes
- **THEN** distributed application source-aware and account-aware authentication limits remain enforced
