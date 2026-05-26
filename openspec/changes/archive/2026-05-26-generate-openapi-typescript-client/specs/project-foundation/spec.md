## ADDED Requirements

### Requirement: OpenAPI client generation workflow

The project foundation SHALL provide a reproducible workflow for generating frontend TypeScript API contracts from the backend OpenAPI schema.

#### Scenario: Developer regenerates frontend API contracts

- **WHEN** a developer changes backend request or response schemas used by the frontend
- **THEN** the repository provides a documented command to regenerate the frontend TypeScript API contracts from FastAPI OpenAPI

#### Scenario: Generated client workflow is discoverable

- **WHEN** a developer inspects the frontend package scripts or project documentation
- **THEN** they can identify how to regenerate and verify the OpenAPI-derived TypeScript contracts
