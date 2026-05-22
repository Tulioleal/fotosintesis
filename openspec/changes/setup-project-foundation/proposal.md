## Why

Fotosintesis AI needs a runnable project baseline before feature work can be implemented safely. This change establishes the frontend, backend, data, storage and local development foundation for the rest of the MVP.

## What Changes

- Create frontend and backend project structure aligned with the MVP technical architecture.
- Configure Next.js, React, TypeScript, SCSS Modules, TanStack Query and Zustand.
- Configure FastAPI, Uvicorn, settings and environment loading.
- Add PostgreSQL + pgvector migration baseline.
- Add object storage abstraction for images and temporary identification assets.
- Add Docker Compose for local frontend, backend, database and optional object storage.
- Add shared DTO/schema contracts for core MVP domains.

## Capabilities

### New Capabilities

- `project-foundation`: project structure, local stack, baseline persistence, storage and shared contracts.

### Modified Capabilities

- None.

## Impact

- Affects repository structure, frontend app bootstrap, backend app bootstrap, database migrations, local infrastructure and shared schema definitions.
