## MODIFIED Requirements

### Requirement: User registration

The system SHALL allow users to create an account with valid name, email and password subject to distributed source-aware registration limits.

#### Scenario: Valid registration

- **WHEN** a user submits valid name, email and password within the active registration limits
- **THEN** the system creates the user with an Argon2id password hash
- **AND** the user has an `email_verified` logical field that does not block login

#### Scenario: Invalid registration

- **WHEN** a user submits empty required fields, invalid email, short password or an already registered email within the active limits
- **THEN** the system prevents registration and shows a recoverable form error

#### Scenario: Registration is limited

- **WHEN** registration attempts from one trusted source identity exhaust the configured registration limit
- **THEN** the system rejects further attempts before performing password hashing or account creation
- **AND** returns the bounded retry contract

#### Scenario: Frontend registration validation

- **WHEN** a user edits the registration form
- **THEN** the frontend validates the form with React Hook Form and Zod

#### Scenario: Backend registration validation

- **WHEN** the backend receives a registration request
- **THEN** it validates the payload with Pydantic and explicit endpoint rules

### Requirement: Login and protected access

The system SHALL allow valid users to log in, SHALL require an authenticated session for private flows, and SHALL constrain credential verification with distributed source-aware and account-aware limits.

#### Scenario: Valid login

- **WHEN** a registered user submits valid credentials within the active limits
- **THEN** Auth.js creates an authenticated session
- **AND** the system redirects the user to `/home`

#### Scenario: Failed login

- **WHEN** a user submits an incorrect password or an email that does not exist within the active limits
- **THEN** the system shows a neutral user-facing error
- **AND** the system logs only a bounded technical reason without exposing whether the email exists

#### Scenario: Login is limited

- **WHEN** a source-aware or normalized account-aware credential limit is exhausted
- **THEN** the system rejects credential verification without performing another password check
- **AND** the login form communicates the bounded retry timing without exposing which limit was reached

#### Scenario: Unauthenticated private frontend access

- **WHEN** a navigation targets Home, identification, search, My Garden, reminders, light meter or assistant without a valid session
- **THEN** the system redirects server-side to `/login`

#### Scenario: Unauthenticated private API access

- **WHEN** a request targets a protected backend API without a valid session
- **THEN** the backend returns unauthorized access with `401`

### Requirement: Password recovery initiation

The system SHALL allow users to initiate password recovery from the authentication screen subject to distributed source-aware and normalized account-aware limits. The recovery response message SHALL be in English and SHALL remain neutral for known and unknown accounts at and below the limit.

#### Scenario: Recovery requested

- **WHEN** a user requests recovery with a valid email format within the active limits
- **THEN** the system generates and persists a recovery token with expiration when applicable
- **AND** shows a neutral English confirmation

#### Scenario: Recovery without email provider

- **WHEN** the recovery request is completed in this slice
- **THEN** the system does not send an email
- **AND** the recovery token and confirmation contract remain prepared for a later email provider integration
- **AND** the neutral English confirmation is the same as in the recovery-requested scenario

#### Scenario: Recovery initiation is limited

- **WHEN** a source-aware or normalized account-aware recovery-initiation limit is exhausted
- **THEN** the system performs no recovery-token write or delivery action
- **AND** known and unknown accounts receive the same neutral response body and equivalent bounded retry contract

## ADDED Requirements

### Requirement: Authentication forms handle bounded retry responses

Authentication forms SHALL recognize the authentication rate-limit response contract, preserve neutral user-facing behavior, and prevent resubmission until the bounded retry period has elapsed.

#### Scenario: Authentication form receives a retry contract

- **WHEN** login, registration, or recovery initiation receives a rate-limit response with `Retry-After`
- **THEN** the form presents recoverable retry timing without sensitive details
- **AND** disables or otherwise prevents submission until retry is permitted
