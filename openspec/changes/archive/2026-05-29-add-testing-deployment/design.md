## Context

This is the release-hardening slice. It should run after or alongside feature slices once enough behavior exists to test meaningfully.

## Goals / Non-Goals

**Goals:**

- Add backend unit and integration coverage for core domains.
- Add frontend component coverage for critical states.
- Add Playwright end-to-end paths for main MVP journeys.
- Provide Kubernetes/GKE deployment manifests.
- Document local setup, environment, mocks, providers, evaluation and deployment.

**Non-Goals:**

- No new product features.
- No production SRE program beyond baseline deployment artifacts and docs.

## Decisions

- Backend tests cover both domain units and API integration points.
- Frontend tests prioritize forms and user-visible state transitions.
- E2E tests cover happy paths plus fallback paths that are critical to MVP reliability.
- Deployment docs must include mocks and provider configuration so development can run without real credentials.

## IaC Decisions

- Infrastructure provisioning SHALL be managed with OpenTofu.
- Kubernetes workload deployment SHALL be managed with plain Kubernetes manifests.
- OpenTofu SHALL provision GKE, Artifact Registry, Cloud SQL for PostgreSQL, Cloud Storage, Secret Manager, IAM and baseline monitoring resources.
- OpenTofu outputs SHALL provide the values required by Kubernetes deployment.
- Secrets SHALL NOT be committed to the repository; runtime secrets SHALL be stored in Secret Manager or injected through Kubernetes secrets.
- Docker Compose remains the local development path and SHALL not be replaced by IaC.

## Risks / Trade-offs

- Writing this slice too early can create brittle tests around unfinished UI; apply when feature contracts are stable enough.
- GKE details may evolve with actual infrastructure choices.
