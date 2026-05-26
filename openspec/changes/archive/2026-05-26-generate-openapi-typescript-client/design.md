## Context

The backend is FastAPI and already exposes an OpenAPI contract from Pydantic response models. The frontend currently imports a typed client from `frontend/src/lib/generated/client.ts`, but that file appears handwritten and there is no repeatable generation command or committed schema artifact proving it matches the backend contract.

This change should preserve the existing security boundary: browser-executed code calls frontend-owned endpoints for protected business data, and server-side frontend code forwards HttpOnly cookies or server-only credentials to the backend.

## Goals / Non-Goals

**Goals:**

- Generate frontend TypeScript API types from the FastAPI OpenAPI schema with a reproducible command.
- Make generated files clearly identifiable as generated and safe to overwrite.
- Keep a small runtime API wrapper where needed for application-specific behavior such as frontend server-boundary calls.
- Ensure `GET /home/summary` and auth support calls consume generated request/response types instead of duplicated DTO definitions.
- Document the regeneration workflow for backend contract changes.
- Add tests or checks that fail when the generated client/types drift from expected frontend usage.

**Non-Goals:**

- No backend API contract redesign beyond exposing or exporting the existing OpenAPI schema.
- No change to authentication semantics, session persistence or protected route behavior.
- No direct browser use of backend session bearer tokens.
- No requirement to generate a full runtime client if generated types plus a typed wrapper are simpler and safer for this stack.

## Decisions

- Use FastAPI's OpenAPI schema as the single source of truth for frontend DTO types.
  - Rationale: backend Pydantic models already define the authoritative request and response shapes.
  - Alternative considered: keep manual types with a transitional marker. This is lower effort but preserves schema-drift risk and does not satisfy the preferred contract.

- Add a committed generation command in the frontend package scripts.
  - Rationale: developers need a stable command to refresh types after backend API changes, and CI can run or verify the same command.
  - Alternative considered: document a manual browser download from `/openapi.json`. This is less reproducible and easier to skip.

- Generate types into a dedicated generated location and keep handwritten runtime behavior outside generated files when possible.
  - Rationale: generated files should be safe to overwrite. App-specific fetch behavior, frontend proxy routes and error handling are easier to maintain in a small handwritten wrapper.
  - Alternative considered: generate and use a full fetch client directly. This can be useful later, but may fight the existing server-side session boundary for protected frontend calls.

- Keep protected Home calls behind the frontend server-side boundary.
  - Rationale: the existing security specs require backend session credentials to remain server-only. Generated types must improve contract safety without changing credential exposure.
  - Alternative considered: call the backend directly from browser code using generated functions. This would conflict with the secure auth session boundary.

- Add drift protection through tests or a verification script.
  - Rationale: generation only helps if developers can detect stale output. A lightweight check is enough for this slice.
  - Alternative considered: rely only on developer discipline. This is the current weakness.

## Risks / Trade-offs

- Generator output may be noisy or unstable across dependency updates -> Pin the generator dependency and keep generated output isolated.
- The backend may need app imports to emit OpenAPI without a running server -> Prefer a script that imports the FastAPI app and writes JSON, with environment defaults suitable for local development.
- Generated runtime clients may not match the frontend auth boundary -> Generate types first and keep security-sensitive request routing in handwritten wrappers.
- CI may become slower if generation starts the backend server -> Prefer schema export by app import, or keep the generation command separate from normal unit tests with a lightweight drift check.

## Migration Plan

1. Add the OpenAPI export/generation tooling and package scripts.
2. Generate TypeScript API types from the current FastAPI schema.
3. Update the existing frontend API wrapper to import generated types for Home and auth support endpoints.
4. Add a generated-file header and documentation for regeneration.
5. Add or update tests/checks to verify the wrapper still typechecks and generated artifacts are present.
6. Remove duplicated DTO definitions from the old handwritten generated client file, or rename handwritten code out of the generated directory.
