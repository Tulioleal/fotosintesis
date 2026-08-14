## ADDED Requirements

### Requirement: Authentication dependency security gate

Frontend CI SHALL verify the installed frozen-lockfile Auth.js dependency shape and SHALL scan production dependencies for high-severity advisories before build or deployment.

#### Scenario: Patched aligned dependency graph is verified

- **WHEN** frontend CI installs dependencies with the frozen lockfile
- **THEN** a deterministic policy check verifies exact `next-auth@5.0.0-beta.32`, no direct `@auth/core`, one reachable transitive core version, and no direct core imports
- **AND** the production dependency advisory scan reports no GHSA-8fpg-xm3f-6cx3 finding

#### Scenario: Authentication dependency policy is violated

- **WHEN** the manifest, installed graph, source imports, or advisory scan contains an affected or unaligned Auth.js dependency
- **THEN** frontend CI fails before image build or deployment

#### Scenario: Root dependency files change

- **WHEN** a pull request or main-branch push changes the root package manifest, pnpm lockfile, or pnpm workspace definition
- **THEN** the frontend validation workflow runs the authentication dependency security gate

### Requirement: Authentication upgrade regression gate

The Auth.js security upgrade SHALL pass focused fail-closed tests and the existing complete frontend validation and authentication journey before deployment.

#### Scenario: Authentication release candidate is verified

- **WHEN** the upgraded frontend is prepared for merge
- **THEN** focused tests cover missing configuration, decode failure, malformed credentials responses, stale backend sessions, credential non-exposure, callback routing, and logout
- **AND** lint, typecheck, full component tests, generated contract verification, production build, and authentication end-to-end tests pass

#### Scenario: Production server starts without Auth.js secrets

- **WHEN** CI starts the built frontend on an isolated local port with both supported Auth.js secret variables removed
- **THEN** a representative private-route request redirects to `/login`
- **AND** the smoke fails if private content or a successful authorization result is returned
- **AND** the production server is terminated after the bounded check
