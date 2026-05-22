## Why

The MVP needs automated verification and a documented deployment path after core feature slices are implemented. This change consolidates backend, frontend, end-to-end, infrastructure and setup documentation work.

## What Changes

- Add backend unit tests for auth, taxonomy validation, providers, RAG filters, ingestion and reminders.
- Add backend integration tests for health, metrics, chat, plant identification, garden, reminders, light measurements and evaluation endpoints.
- Add frontend component tests for forms, Home, candidate selection, profile, garden, reminders and light meter states.
- Add Playwright end-to-end tests for auth, Home navigation, identification to profile, garden save, reminder creation, assistant RAG and light fallback.
- Add Kubernetes/GKE manifests or Helm chart for frontend, backend and supporting cloud resources.
- Document local setup, required environment variables, mocks, provider configuration, evaluation run and deployment path.

## Capabilities

### New Capabilities

- `testing-deployment`: automated test coverage, deployment manifests and operational documentation.

### Modified Capabilities

- None.

## Impact

- Affects test suites, CI readiness, Kubernetes/GKE deployment files and developer/operator documentation.
