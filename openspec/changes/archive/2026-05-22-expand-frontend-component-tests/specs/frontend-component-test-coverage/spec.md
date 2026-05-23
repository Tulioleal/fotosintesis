## ADDED Requirements

### Requirement: Auth form component tests
The system SHALL include component tests for auth forms that verify user-facing rendering, validation and submitted boundary calls.

#### Scenario: Login form is tested
- **WHEN** frontend component tests run
- **THEN** they verify `LoginForm` renders the email and password controls, submits valid credentials through the Auth.js sign-in boundary and displays the configured invalid-credential error when sign-in fails

#### Scenario: Recovery form is tested
- **WHEN** frontend component tests run
- **THEN** they verify `RecoveryForm` renders the email control, submits a recovery request through the generated API client and displays the neutral recovery confirmation message

#### Scenario: Registration validation is tested
- **WHEN** frontend component tests run
- **THEN** they verify `RegisterForm` displays validation errors for invalid registration input before submitting to the generated API client

### Requirement: Home dashboard state component tests
The system SHALL include component tests for Home dashboard loading, error and retry states in addition to authenticated success and empty states.

#### Scenario: Home loading state is tested
- **WHEN** frontend component tests run while session or summary data is loading
- **THEN** they verify `HomeDashboard` renders the accessible Home loading skeleton

#### Scenario: Home error state is tested
- **WHEN** frontend component tests run with a failed Home summary request
- **THEN** they verify `HomeDashboard` renders the user-facing Home error message and retry action

#### Scenario: Home retry behavior is tested
- **WHEN** a user activates the Home retry action after an error
- **THEN** the component tests verify the Home summary request is attempted again through the generated API client
