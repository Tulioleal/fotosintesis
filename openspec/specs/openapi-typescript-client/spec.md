## Purpose

Define generation, usage and verification of frontend TypeScript API contracts from the FastAPI OpenAPI schema.

## Requirements

### Requirement: OpenAPI-generated TypeScript contracts

The system SHALL generate frontend TypeScript API contracts from the FastAPI OpenAPI schema using a repeatable repository command.

#### Scenario: Client contracts are regenerated

- **WHEN** a developer runs the documented OpenAPI client generation command
- **THEN** the command obtains the current FastAPI OpenAPI schema and updates the frontend TypeScript API contract artifacts

#### Scenario: Generated artifacts are identifiable

- **WHEN** a developer opens a generated TypeScript contract file
- **THEN** the file clearly indicates that it is generated and should not be edited by hand

### Requirement: Generated contracts are used by frontend API wrappers

The frontend SHALL use generated OpenAPI TypeScript contracts for backend request and response shapes consumed by business and auth support API wrappers.

#### Scenario: Home summary uses generated types

- **WHEN** the frontend wrapper consumes `GET /home/summary`
- **THEN** its response type comes from the generated OpenAPI TypeScript contracts rather than a manually duplicated DTO definition

#### Scenario: Auth support calls use generated types

- **WHEN** the frontend wrapper calls registration or password recovery support endpoints
- **THEN** request and response types come from the generated OpenAPI TypeScript contracts rather than manually duplicated DTO definitions

### Requirement: Garden API wrappers use generated contracts

The frontend SHALL use generated OpenAPI TypeScript contracts for garden request and response shapes consumed by garden API wrapper functions.

#### Scenario: Garden list uses generated response type

- **WHEN** the frontend wrapper consumes `GET /garden`
- **THEN** its response type comes from the generated OpenAPI TypeScript contracts rather than a manually duplicated garden list type

#### Scenario: Garden detail uses generated response type

- **WHEN** the frontend wrapper consumes `GET /garden/{garden_id}`
- **THEN** its response type comes from the generated OpenAPI TypeScript contracts rather than a manually duplicated garden detail type

#### Scenario: Garden save uses generated request and response types

- **WHEN** the frontend wrapper consumes `POST /garden`
- **THEN** its request and response types come from the generated OpenAPI TypeScript contracts rather than manually duplicated DTO definitions

#### Scenario: Garden delete uses generated response type

- **WHEN** the frontend wrapper consumes `DELETE /garden/{garden_id}`
- **THEN** its response type comes from the generated OpenAPI TypeScript contracts rather than a manually duplicated delete response type

#### Scenario: Browser garden calls preserve the route boundary

- **WHEN** browser-executed frontend code needs protected garden data
- **THEN** it calls the frontend-owned garden API boundary endpoints and does not call the protected backend API directly

### Requirement: Generated client preserves the secure session boundary

The generated TypeScript client workflow SHALL preserve the existing server-side session boundary for protected backend endpoints.

#### Scenario: Browser requests protected Home data

- **WHEN** browser-executed frontend code needs Home summary data
- **THEN** it calls the frontend-owned Home summary boundary endpoint and does not attach an opaque backend session token or backend bearer credential

#### Scenario: Server boundary calls protected backend data

- **WHEN** server-side frontend code forwards a protected backend request
- **THEN** it may use generated contracts for type safety while keeping backend credentials server-only

### Requirement: OpenAPI generation drift protection

The system SHALL include an automated check or test that protects against stale or missing generated OpenAPI TypeScript artifacts.

#### Scenario: Verification runs after generation setup

- **WHEN** frontend verification commands run
- **THEN** they fail if the generated contracts needed by the frontend API wrappers are missing or incompatible with current TypeScript usage

#### Scenario: Backend contract changes

- **WHEN** a backend API schema change affects frontend-consumed endpoints
- **THEN** regenerating the TypeScript contracts updates the frontend types used by the wrappers

### Requirement: Assistant chat generated taxonomy fields

The frontend SHALL regenerate and consume OpenAPI TypeScript contracts that include optional nullable `plant_binomial_name` and `plant_scientific_name` assistant chat request fields.

#### Scenario: Generated assistant request includes taxonomy fields

- **WHEN** OpenAPI TypeScript generation is run after the backend assistant schema update
- **THEN** the generated assistant chat request type includes `plant_binomial_name` and `plant_scientific_name` as optional nullable fields

#### Scenario: Frontend chat client sends taxonomy fields

- **WHEN** frontend assistant chat code sends a request with binomial and scientific query context
- **THEN** the frontend API wrapper accepts and forwards `plant_binomial_name` and `plant_scientific_name` without manually diverging from the generated contract
