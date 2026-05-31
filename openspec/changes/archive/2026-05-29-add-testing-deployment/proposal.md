## Why

The MVP needs automated verification and a documented deployment path after core feature slices are implemented. This change consolidates backend, frontend, end-to-end, infrastructure and setup documentation work.

## What Changes

- Add backend unit tests for auth, taxonomy validation, providers, RAG filters, ingestion and reminders.
- Add backend integration tests for health, metrics, chat, plant identification, garden, reminders, light measurements and evaluation endpoints.
- Add frontend component tests for forms, Home, candidate selection, profile, garden, reminders and light meter states.
- Add Playwright end-to-end tests for auth, Home navigation, identification to profile, garden save, reminder creation, assistant RAG and light fallback.
- Add OpenTofu-based Infrastructure as Code for provisioning GCP infrastructure, including GKE, Artifact Registry, Cloud SQL for PostgreSQL, Cloud Storage, Secret Manager, IAM and baseline monitoring. Add Kubernetes manifests for deploying frontend, backend and supporting workloads onto the provisioned cluster.
- Document local setup, required environment variables, mocks, provider configuration, evaluation run and deployment path.

## Capabilities

### New Capabilities

- `testing-deployment`: automated test coverage, deployment manifests and operational documentation.

### Modified Capabilities

- None.

## Impact

- Affects test suites, CI readiness, OpenTofu infrastructure modules, Kubernetes deployment files, cloud resource configuration and developer/operator documentation.
