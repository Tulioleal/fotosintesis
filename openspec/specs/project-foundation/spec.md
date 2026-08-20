## Purpose

Define the runnable project foundation for Fotosintesis AI, including frontend, backend, local infrastructure, baseline persistence, object storage and shared MVP contracts.
## Requirements
### Requirement: Frontend baseline

The system SHALL include a Next.js, React and TypeScript frontend configured with SCSS Modules, TanStack Query and Zustand.

#### Scenario: Frontend app starts locally

- **WHEN** the local frontend command runs with valid environment configuration
- **THEN** the system serves the frontend application and can render the base app shell

### Requirement: Backend baseline

The system SHALL include a FastAPI + Uvicorn backend with application settings and environment loading.

#### Scenario: Backend app starts locally

- **WHEN** the local backend command runs with valid environment configuration
- **THEN** the system starts the API application and exposes a base service entrypoint

### Requirement: Persistence and storage baseline

The system SHALL include PostgreSQL + pgvector migrations and an object storage abstraction for user images and temporary identification assets. The object storage abstraction SHALL support local filesystem storage for development and GCS-backed storage for GCP runtime environments.

#### Scenario: Baseline migration applied

- **WHEN** database migrations are applied to a clean local database
- **THEN** the system enables the baseline schema and vector extension needed by later features

#### Scenario: Local object storage remains available
- **WHEN** the backend runs in local development configuration
- **THEN** user image and temporary identification assets are stored through the local filesystem storage implementation without requiring GCP credentials

#### Scenario: GCP object storage uses GCS
- **WHEN** the backend runs in a GCP environment with object storage provider configured for GCS
- **THEN** user image and temporary identification assets are stored in the configured GCS bucket through the backend storage abstraction

#### Scenario: GCS access uses workload identity
- **WHEN** backend GCS storage is used in GKE
- **THEN** storage access is authorized through the backend workload identity service account and does not require static object storage access keys in Kubernetes secrets

### Requirement: Local development stack

The system SHALL include Docker Compose services for frontend, backend, postgres and optional local object storage.

#### Scenario: Local stack starts

- **WHEN** the documented Docker Compose stack is started
- **THEN** the required local services become available for development without real external providers

### Requirement: Shared MVP contracts

The system SHALL define common DTO/schema contracts for users, plants, garden, reminders, light measurements, conversations and evaluation.

#### Scenario: Feature slices use shared contracts

- **WHEN** a later feature implements an API or frontend integration
- **THEN** it can reuse the shared contract names and payload shapes instead of inventing incompatible models

### Requirement: OpenAPI client generation workflow

The project foundation SHALL provide a reproducible workflow for generating frontend TypeScript API contracts from the backend OpenAPI schema.

#### Scenario: Developer regenerates frontend API contracts

- **WHEN** a developer changes backend request or response schemas used by the frontend
- **THEN** the repository provides a documented command to regenerate the frontend TypeScript API contracts from FastAPI OpenAPI

#### Scenario: Generated client workflow is discoverable

- **WHEN** a developer inspects the frontend package scripts or project documentation
- **THEN** they can identify how to regenerate and verify the OpenAPI-derived TypeScript contracts

### Requirement: Home navigation labels are English

The home-screen access labels exposed through the backend `GET /home/summary` API SHALL be in English. The six access labels are `My Garden`, `Identify plant`, `Search plants`, `Light meter`, `Reminders`, and `Assistant`. Backend services and shared DTOs that produce these labels SHALL NOT emit Spanish translations for them; any consumer that hardcoded Spanish fallbacks for these labels MUST be updated to match the English API output.

#### Scenario: Home summary returns English labels

- **WHEN** an authenticated user requests `GET /home/summary`
- **THEN** the response's `access[]` array contains entries whose `label` field uses one of the six English labels `My Garden`, `Identify plant`, `Search plants`, `Light meter`, `Reminders`, or `Assistant`
- **AND** the response does not contain any Spanish translation of those labels (such as `Mi Jardín`, `Identificar planta`, `Buscar plantas`, `Medidor de luz`, `Recordatorios`, or `Asistente`)

#### Scenario: Frontend consumes English labels

- **WHEN** the frontend renders the home access grid from `GET /home/summary`
- **THEN** it uses the `label` field returned by the API directly
- **AND** it does not apply a Spanish fallback translation for these six access entries

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

### Requirement: Object storage deletion compensation

The object storage abstraction SHALL expose a best-effort delete operation by object path so that callers can remove a stored object when subsequent durable work fails. Cleanup failures SHALL be logged with the object identifier and SHALL NOT include image content.

#### Scenario: Storage interface exposes delete operation

- **WHEN** a caller has stored an object and later durable work fails
- **THEN** the caller can invoke a delete operation keyed by the stored object path to remove the object on a best-effort basis

#### Scenario: Cleanup failure is logged without content

- **WHEN** a best-effort object deletion fails
- **THEN** the failure is logged with the object path or identifier
- **AND** the log does not include the image bytes or any decoded image content

