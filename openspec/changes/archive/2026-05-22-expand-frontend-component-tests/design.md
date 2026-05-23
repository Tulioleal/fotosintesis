## Context

The current frontend component tests cover a narrow slice of the auth and Home dashboard UI. `RegisterForm.test.tsx` verifies that fields render, while `HomeDashboard.test.tsx` covers the authenticated empty state and confirms the Home data client is called without bearer-token arguments. There are no component tests for `LoginForm` or `RecoveryForm`, and Home loading, error and retry states are untested.

This change is test-only. It should preserve component behavior and use the existing frontend test stack: Vitest, React Testing Library, user-event patterns where needed, TanStack Query test wrappers and module mocks for Next.js/Auth.js boundaries.

## Goals / Non-Goals

**Goals:**

- Add meaningful regression coverage for login, recovery, registration validation and Home dashboard state handling.
- Keep tests user-facing by asserting labels, buttons, status text and mocked boundary calls rather than implementation details.
- Isolate each test from shared query cache, mocked auth state and mocked API calls.
- Verify Home retry behavior through the rendered retry button and mocked `getHomeSummary` calls.

**Non-Goals:**

- Change auth form, Home dashboard or generated API client runtime behavior.
- Add new test frameworks, browser end-to-end tests or visual regression tooling.
- Broaden backend auth, persistence or session-boundary requirements.

## Decisions

- Use React Testing Library interaction tests rather than snapshot tests because the gaps are behavioral: validation messages, submit calls, loading/error rendering and retry actions.
- Mock external boundaries at the module level because these components depend on Next.js navigation/search params, Auth.js session/sign-in state and the generated API client.
- Create fresh `QueryClient` instances per Home dashboard render because shared cache would hide loading/error transitions and make retry assertions order-dependent.
- Keep the new coverage alongside the existing component test files because the change is localized and does not require shared test helpers unless duplication becomes substantial during implementation.

## Risks / Trade-offs

- Mocked form and data clients can drift from real integration behavior -> Prefer user-visible assertions plus explicit checks for the submitted payloads and retry calls.
- Async form validation can make tests flaky if assertions do not wait for UI updates -> Use `findBy*` or `waitFor` around validation, submission and retry assertions.
- TanStack Query retries can affect call counts in error tests -> Configure the test `QueryClient` defaults or mock sequence carefully so retry behavior remains deterministic.
