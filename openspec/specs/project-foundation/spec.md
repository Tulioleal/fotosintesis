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
