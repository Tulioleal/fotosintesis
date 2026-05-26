## 1. OpenAPI Export And Generation Setup

- [x] 1.1 Add a backend OpenAPI schema export script or command that writes the current FastAPI OpenAPI JSON without manual browser steps
- [x] 1.2 Add the frontend OpenAPI TypeScript generator dependency and pin it in the workspace lockfile
- [x] 1.3 Add package scripts for exporting the schema, generating TypeScript contracts and verifying generated output
- [x] 1.4 Document the client regeneration workflow in the project README or frontend documentation

## 2. Generated Type Artifacts

- [x] 2.1 Generate TypeScript API contracts from the current FastAPI OpenAPI schema into a dedicated generated location
- [x] 2.2 Ensure generated files include a clear generated-file header and are safe to overwrite
- [x] 2.3 Remove manual DTO definitions from `frontend/src/lib/generated/client.ts` or move handwritten runtime code outside the generated artifact path

## 3. Frontend Client Integration

- [x] 3.1 Update the frontend API wrapper to import generated types for registration request/response payloads
- [x] 3.2 Update the frontend API wrapper to import generated types for password recovery request/response payloads
- [x] 3.3 Update the Home summary wrapper to use generated response types while preserving the frontend-owned `/api/home/summary` server boundary
- [x] 3.4 Confirm browser-executed code still does not send backend session bearer tokens or expose opaque backend credentials

## 4. Verification

- [x] 4.1 Add or update tests/checks that fail when generated contracts required by frontend wrappers are missing or incompatible
- [x] 4.2 Run frontend typecheck and unit tests after generated type integration
- [x] 4.3 Run backend tests to confirm OpenAPI export changes do not alter API behavior
- [x] 4.4 Run OpenSpec validation for `generate-openapi-typescript-client`
