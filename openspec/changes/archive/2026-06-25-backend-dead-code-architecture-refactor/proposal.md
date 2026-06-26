## Why

The backend has accumulated large god-files, verified dead code, duplicate provider fallback logic, and one provider-to-assistant layering violation, making safe maintenance and review increasingly expensive. This change reduces refactor risk by removing verified dead code, splitting oversized modules along existing capability seams, and adding enforceable architecture guardrails without changing runtime behavior or the HTTP API.

## What Changes

- Delete verified unused backend code, including unused schema files, unused helpers, unused settings fields, unused observability helpers, and tracked build artifacts.
- Split oversized backend modules in `app/assistant/`, `app/providers/`, and `app/knowledge/` into capability-focused packages while preserving public imports through temporary re-export shims during migration.
- Extract shared provider schemas, provider errors, fallback-chain behavior, and repository base behavior into explicit provider/database seams.
- Remove the `app/providers/gemini.py` dependency on `app/assistant/care_contracts.py` by moving shared provider schema shapes into the provider layer.
- Split the large assistant integration test file after source modules move, preserving coverage and existing behavior.
- Add CI enforcement for per-layer file-size limits and architecture layering rules.
- Verify that `ruff check`, `pytest`, graph topology, and OpenAPI output remain stable across the refactor.

## Capabilities

### New Capabilities

- `backend-architecture-governance`: Defines backend architecture, layering, file-size, dead-code-removal, and refactor verification requirements for the FastAPI/LangGraph service.

### Modified Capabilities

- None. This change is intended to preserve existing product behavior, API contracts, provider selection behavior, LangGraph runtime behavior, and multilingual plant-care semantics.

## Impact

- Affected code: `backend/app/assistant/`, `backend/app/providers/`, `backend/app/knowledge/`, `backend/app/db/`, `backend/app/core/`, `backend/app/observability/`, `backend/app/schemas/`, backend tests, `.gitignore`, and CI scripts/configuration.
- APIs: No intended HTTP API, OpenAPI schema, provider runtime selection, LangGraph topology, or user-facing behavior changes.
- Dependencies: No new runtime dependency is planned; architecture checks may use a lightweight script or existing lint/test tooling.
- Systems: Backend CI will enforce new file-size and layering constraints after the refactor completes.
