## Why

Frontend component test coverage is below the expected level for critical auth and Home dashboard flows. Expanding these tests now reduces regression risk around validation, loading, error and retry states before further feature work builds on these screens.

## What Changes

- Add React Testing Library coverage for `LoginForm` rendering and submission behavior.
- Add React Testing Library coverage for `RecoveryForm` rendering and submission behavior.
- Expand `RegisterForm` tests to cover validation errors, not just field rendering.
- Expand `HomeDashboard` tests to cover loading skeleton, error messaging and retry behavior in addition to existing empty/success paths.
- No runtime behavior, API contract or dependency changes are intended.

## Capabilities

### New Capabilities

- `frontend-component-test-coverage`: Defines expected frontend component test coverage for auth forms and Home dashboard states.

### Modified Capabilities

None.

## Impact

- Affected tests: `frontend/src/components/auth/*.test.tsx`, `frontend/src/components/home/HomeDashboard.test.tsx`.
- Affected components under test: `LoginForm`, `RecoveryForm`, `RegisterForm` and `HomeDashboard`.
- No production APIs, backend behavior, database schema or external dependencies are expected to change.
