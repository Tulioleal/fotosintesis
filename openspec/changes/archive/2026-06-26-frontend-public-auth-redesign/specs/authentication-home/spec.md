## ADDED Requirements

### Requirement: Public authentication entry preserves existing behavior
The redesigned public and authentication entry flow SHALL preserve the existing authentication, registration, recovery, redirect, callback URL, and session behavior.

#### Scenario: Login behavior is preserved
- **WHEN** a user submits valid credentials from the redesigned login form
- **THEN** Auth.js creates the authenticated session using the existing credentials flow
- **AND** the user is redirected to the current callback URL when present or `/home` otherwise

#### Scenario: Login failure behavior is preserved
- **WHEN** a user submits invalid credentials from the redesigned login form
- **THEN** the form shows the existing neutral recoverable error behavior without exposing whether the email exists

#### Scenario: Registration behavior is preserved
- **WHEN** a user submits valid registration values from the redesigned registration form
- **THEN** the existing registration API flow creates the account
- **AND** the user is sent through the existing registration success flow to login with the registered-success notice

#### Scenario: Registration validation is preserved
- **WHEN** a user submits empty required fields, invalid email, short password, or a duplicate account from the redesigned registration form
- **THEN** the existing frontend and backend validation behavior prevents registration and shows recoverable form errors

#### Scenario: Recovery behavior is preserved
- **WHEN** a user submits a valid email format from the redesigned recovery form
- **THEN** the existing recovery request flow runs and shows the existing neutral confirmation contract
- **AND** this change does not add an email provider or change recovery token semantics

#### Scenario: Protected route redirect remains unchanged
- **WHEN** an unauthenticated user navigates to a private route after the public/auth redesign
- **THEN** the existing server-side route protection redirects to `/login` with the current callback behavior

### Requirement: Auth form accessibility remains stable
The redesigned authentication forms SHALL preserve accessible labels, button names, disabled states, and feedback semantics needed by users and automated tests unless a requirement explicitly updates visible copy.

#### Scenario: Login form remains accessible
- **WHEN** assistive technology or tests inspect the redesigned login form
- **THEN** the email and password controls remain reachable by their existing accessible labels
- **AND** the primary submit action remains reachable by its existing accessible button name unless the implementation updates tests for an explicitly specified copy change

#### Scenario: Registration form remains accessible
- **WHEN** assistive technology or tests inspect the redesigned registration form
- **THEN** the name, email, and password controls remain reachable by their existing accessible labels
- **AND** the primary submit action remains reachable by its existing accessible button name unless the implementation updates tests for an explicitly specified copy change

#### Scenario: Recovery form remains accessible
- **WHEN** assistive technology or tests inspect the redesigned recovery form
- **THEN** the email control and recovery submit action remain reachable by their existing accessible labels and button name unless the implementation updates tests for an explicitly specified copy change

#### Scenario: Decorative visuals do not replace labels
- **WHEN** the redesigned auth forms add icons, botanical imagery, or visual field adornments
- **THEN** those decorative visuals do not replace explicit accessible labels, form errors, disabled states, or success/recovery feedback text

### Requirement: Public/auth redesign excludes private feature changes
The public and authentication redesign SHALL NOT redesign private feature pages or alter authenticated feature behavior.

#### Scenario: Private pages remain out of scope
- **WHEN** this change is implemented
- **THEN** private feature pages such as Home, identification, search, light meter, reminders, My Garden, garden details, plant profiles, and assistant are not visually redesigned as part of this change

#### Scenario: Existing private behavior remains intact
- **WHEN** tests exercise authenticated Home and placeholder private routes after the public/auth redesign
- **THEN** existing private route rendering, navigation, data fetching, placeholder behavior, and session handling continue to satisfy their current requirements
