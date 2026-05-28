## ADDED Requirements

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
