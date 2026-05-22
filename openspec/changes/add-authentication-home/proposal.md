## Why

The MVP needs a protected mobile-first entry point before private plant, assistant and garden features can be used. Authentication and Home establish the first complete user-facing flow.

## What Changes

- Implement registration with required-field, email, password length and duplicate email validation.
- Implement login, session handling and protected routes/APIs.
- Implement password recovery initiation.
- Build welcome and auth screens with loading, disabled and error states.
- Build Home with identification CTA, search, medidor de luz, recordatorios, Mi Jardin and assistant access.
- Implement Home empty, loading, error and retry states.
- Apply Fotosintesis visual identity, bottom navigation and Spanish tone consistently.

## Capabilities

### New Capabilities

- `authentication-home`: authentication, protected access and mobile-first Home experience.

### Modified Capabilities

- None.

## Impact

- Affects frontend auth screens, session state, backend auth APIs, protected navigation and Home UI.
