## 1. Backend Suggestion Operation

- [x] 1.1 Add request and response schemas for a suggestion or clarification result (discriminated union), reusing existing assistant structured-output contracts.
- [x] 1.2 Add a backend operation that accepts a selected garden plant and optional user request, resolves confirmed taxonomy through ownership checks, and loads profile evidence, garden location, notes, active reminders, and timezone.
- [x] 1.3 Generate schema-validated suggestions through the configured assistant model, loading a valid light measurement only when semantic classification requires it.
- [x] 1.4 Return evidence context, confidence, limitations, and a concise justification with each suggestion.
- [x] 1.5 Return a structured clarification response when date, time, timezone, or recurrence is missing, without inventing defaults.

## 2. Duplicate Detection

- [x] 2.1 Detect equivalent active reminders (garden plant, schema-validated action intent, schedule overlap) before returning a suggestion and return an existing reminder reference instead of a duplicate draft.
- [x] 2.2 Add a transactional duplicate recheck to the reminder creation path.

## 3. API and Frontend Wiring

- [x] 3.1 Expose an authenticated API route (and frontend BFF route if required) for suggestion generation and update generated OpenAPI TypeScript contracts.
- [x] 3.2 Replace the reminders page local `buildSuggestions` and `suggestActionFor` generators with backend calls, preserving the existing confirmation card UI.
- [x] 3.3 Ensure accepted suggestions create reminders through the existing reminders API and store the suggestion justification.

## 4. Metrics

- [x] 4.1 Add metrics for accepted, edited, rejected, clarified, and duplicate suggestions.

## 5. Verification

- [x] 5.1 Remove reminders-page heuristic tests and add backend interaction tests for complete, incomplete, duplicate, insufficient-evidence, and provider-failure cases.
- [x] 5.2 Add regression tests proving AI-labeled suggestions no longer originate from tomorrow, 09:00, weekly, or language-specific frontend regex defaults, and that non-English or paraphrased evidence reaches semantic judging without keyword matches.
- [x] 5.3 Add tests proving timezone-aware suggestion fields and eligible light context follow the existing scheduling and light-context contracts.
- [x] 5.4 Run backend and frontend lint, typecheck, and test suites.
