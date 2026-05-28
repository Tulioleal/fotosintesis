## Context

Reminder behavior spans a client component, authenticated FastAPI routes, and an async SQLAlchemy repository. The change adds regression tests around the existing behavior without introducing new runtime paths, database schema changes, or API contract changes.

## Goals / Non-Goals

**Goals:**
- Cover `RemindersManager` loading, validation, create, edit/update, complete, delete, suggestion, and error paths with focused Vitest/Testing Library tests.
- Cover reminder API route success and failure behavior with authenticated `httpx` ASGI tests using the existing in-memory test database fixtures.
- Cover repository persistence behavior directly, including plant ownership checks, listing/filtering, active reminder counts, completion recurrence, deletion, and missing-record behavior.

**Non-Goals:**
- Change reminder runtime behavior, API schemas, or database tables.
- Add end-to-end browser coverage.
- Introduce new test infrastructure unless existing helpers are insufficient.

## Decisions

- Use existing frontend test conventions: render the component through the project query-client helper, mock `@/lib/api/client`, and mock `next/navigation` search params where needed. This keeps tests close to current component tests and avoids coupling them to network behavior.
- Use existing backend ASGI route-test conventions for `backend/app/api/reminders.py`. Tests should create authenticated users and fixture data through repository/table helpers, then exercise the public HTTP endpoints rather than route functions directly.
- Add direct repository tests for `backend/app/reminders/repository.py` where persistence invariants are easier to verify without HTTP serialization noise, especially active reminder count changes and recurring completion behavior.
- Prefer focused assertions over broad snapshots. Each test should target one behavior or invariant and use stable Spanish UI/API messages where those messages are part of current observable behavior.

## Risks / Trade-offs

- Broad component interaction tests can become brittle if labels or copy change. Mitigation: assert user-visible behavior that matters and keep setup data minimal.
- Repository and route tests may overlap on happy paths. Mitigation: route tests focus on request/response/auth/validation semantics while repository tests focus on persistence invariants.
- Time-sensitive validation can be flaky. Mitigation: use future dates for success cases and explicitly past dates only for validation rejection cases.
