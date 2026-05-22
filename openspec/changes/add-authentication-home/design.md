## Context

This slice creates the first authenticated product surface. It depends on the project foundation and should keep integrations to later features as navigational entry points or placeholders until those features exist.

## Goals / Non-Goals

**Goals:**

- Support registration, login, session persistence and protected access.
- Provide a Home that reflects the intended MVP navigation and visual language.
- Handle loading, disabled, empty, error and retry states from the start.

**Non-Goals:**

- No completed plant identification, garden, reminders, assistant or light meter implementation.
- No advanced account management beyond password recovery initiation.

## Decisions

- Auth validation is enforced server-side and reflected in frontend form states.
- Login errors avoid revealing whether an email exists.
- Home prioritizes plant identification as the main CTA and exposes secondary access to search, light meter, reminders, Mi Jardin and assistant.
- Protected routes and APIs share the same session requirement.

## Risks / Trade-offs

- Password recovery may need a provider later; this slice only initiates the flow and exposes neutral confirmation copy.
- Home links to features that may still be pending; use disabled, placeholder or coming-soon states only where necessary.
