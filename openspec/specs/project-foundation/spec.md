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

The system SHALL include PostgreSQL + pgvector migrations and an object storage abstraction for user images and temporary identification assets.

#### Scenario: Baseline migration applied

- **WHEN** database migrations are applied to a clean local database
- **THEN** the system enables the baseline schema and vector extension needed by later features

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
