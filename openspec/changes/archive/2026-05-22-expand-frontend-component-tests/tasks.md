## 1. Auth Form Tests

- [x] 1.1 Add `LoginForm` component tests that mock `next-auth/react` sign-in and `next/navigation` search params.
- [x] 1.2 Verify `LoginForm` renders email/password controls, submits valid credentials with the expected callback URL and displays the invalid-credential error when sign-in fails.
- [x] 1.3 Add `RecoveryForm` component tests that mock the generated API client recovery request.
- [x] 1.4 Verify `RecoveryForm` renders the email control, submits the entered email and displays the neutral recovery confirmation message.
- [x] 1.5 Expand `RegisterForm` tests to submit invalid registration input and assert validation errors appear without calling `apiClient.register`.

## 2. Home Dashboard Tests

- [x] 2.1 Update the Home dashboard test setup so each test uses isolated `useSession`, `getHomeSummary` and `QueryClient` state.
- [x] 2.2 Add a loading-state test that verifies the accessible `Cargando Home` skeleton is rendered while session or summary data is loading.
- [x] 2.3 Add an error-state test that mocks a failed Home summary request and verifies the error heading, explanatory text and retry button.
- [x] 2.4 Add a retry-behavior test that clicks `Reintentar` after an error and verifies `getHomeSummary` is called again.

## 3. Verification

- [x] 3.1 Run the frontend component test suite or targeted Vitest files for auth and Home dashboard components.
- [x] 3.2 Fix any test isolation, async assertion or mock-reset issues found during verification.
