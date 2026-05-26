## Why

The frontend currently keeps backend DTOs in a file named like generated code, but there is no generator command, OpenAPI source artifact or generated-file marker proving those types came from FastAPI OpenAPI. This creates a schema-drift risk for protected business endpoints and leaves the typed-client contract from the authentication Home slice ambiguous.

## What Changes

- Add a repeatable frontend command that obtains the FastAPI OpenAPI schema and regenerates TypeScript endpoint types/client code.
- Replace or update the current handwritten `frontend/src/lib/generated/client.ts` flow so generated artifacts are clearly machine-generated and reproducible.
- Keep protected browser calls routed through the existing frontend server-side boundary; generated types must not expose backend session bearer tokens to client components.
- Add tests or checks that verify the generated client is current enough for `GET /home/summary` and auth support calls used by the frontend.
- Document how developers regenerate the client after backend API contract changes.

## Capabilities

### New Capabilities

- `openapi-typescript-client`: generation, usage and verification of the frontend TypeScript client from the FastAPI OpenAPI contract.

### Modified Capabilities

- `project-foundation`: require the runnable project foundation to include a reproducible OpenAPI-to-TypeScript client generation workflow.

## Impact

- Affects frontend client code under `frontend/src/lib/generated/` or an equivalent generated-client location.
- Affects frontend package scripts and development documentation for client regeneration.
- May add a frontend development dependency for OpenAPI TypeScript generation.
- May add a backend or script entrypoint that exports the FastAPI OpenAPI schema without requiring manual browser access.
- Affects tests that mock or import the generated API client.
