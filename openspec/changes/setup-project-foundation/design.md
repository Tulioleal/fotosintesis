## Context

This is the first implementation slice under `add-fotosintesis-ai-mvp`. It creates only the reusable foundation needed by later slices; it does not implement auth, plant identification, RAG, assistant behavior or production deployment.

## Goals / Non-Goals

**Goals:**

- Provide a working local development stack.
- Keep frontend and backend boundaries explicit.
- Establish typed contracts before feature endpoints depend on them.
- Prepare PostgreSQL + pgvector and object storage abstractions without provider-specific coupling.

**Non-Goals:**

- No real MaaS, LLM, RAG, assistant or GBIF integration.
- No finished user-facing feature flows beyond app shell bootstrapping.
- No cloud deployment manifests.

## Decisions

- Frontend uses Next.js, React, TypeScript, SCSS Modules, TanStack Query for server state and Zustand only for transient UI state.
- Backend uses FastAPI + Uvicorn with environment-driven settings.
- Database baseline uses PostgreSQL with pgvector enabled from the start.
- Images are referenced through an object storage abstraction rather than persisted as database blobs.
- DTO/schema contracts cover users, plants, garden, reminders, light measurements, conversations and evaluation so later changes share names and payload shapes.

## Risks / Trade-offs

- Creating too much framework code up front can slow feature delivery, so this slice should stop at the minimal runnable baseline.
- DTOs may evolve as feature slices mature; later changes can modify contracts through their own specs.
