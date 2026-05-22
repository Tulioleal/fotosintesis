## ADDED Requirements

### Requirement: User registration

The system SHALL allow users to create an account with valid name, email and password.

#### Scenario: Invalid registration

- **WHEN** a user submits empty required fields, invalid email, short password or an already registered email
- **THEN** the system prevents registration and shows a recoverable form error

### Requirement: Login and protected access

The system SHALL allow valid users to log in and SHALL require an authenticated session for private flows.

#### Scenario: Unauthenticated private access

- **WHEN** a request or navigation targets Home, identification, Mi Jardin, reminders, light meter or assistant without a valid session
- **THEN** the system redirects to authentication or returns unauthorized access as appropriate

### Requirement: Password recovery initiation

The system SHALL allow users to initiate password recovery from the authentication screen.

#### Scenario: Recovery requested

- **WHEN** a user requests recovery with a valid email format
- **THEN** the system starts the recovery flow and shows a neutral confirmation

### Requirement: Home mobile-first

The system SHALL show an authenticated mobile-first Home with access to identification, search, light meter, reminders, Mi Jardin and assistant.

#### Scenario: Home opens for authenticated user

- **WHEN** an authenticated user opens Home
- **THEN** the system shows primary identification CTA, secondary feature access and bottom navigation with the active section

### Requirement: Home states and identity

Home SHALL include loading, error, empty and retry states while applying the Fotosintesis visual identity and chosen Spanish tone.

#### Scenario: Home data fails

- **WHEN** Home data cannot be refreshed
- **THEN** the system keeps the base interface usable, explains the failure and offers retry
