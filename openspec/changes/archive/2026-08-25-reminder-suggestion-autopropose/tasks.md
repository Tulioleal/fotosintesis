## 1. Backend Proposal Contract

- [x] 1.1 Drop `timezone` from `_SUGGESTION_SCHEMA`; service stamps effective zone from stored user timezone.
- [x] 1.2 Rewrite `_suggestion_prompt`: require a concrete derived date/time/recurrence with justification; ground it with current local date/time + zone key; nulls only when genuinely undeterminable.
- [x] 1.3 Clarification reserved for undeterminable fields and unset account timezone.

## 2. Frontend Suggestion UX

- [x] 2.1 "Editar antes de guardar" action prefills the create form from the proposal and closes the suggestion panel.
- [x] 2.2 Optional one-line context input feeding `request`.
- [x] 2.3 Promote the AI entry as primary above the manual form ("Crear manualmente" secondary).

## 3. Timezone Decluttering

- [x] 3.1 Create form: collapse Zona horaria under "Opciones avanzadas".
- [x] 3.2 Preference card prefills browser-detected IANA zone when account unset, with device-detected hint.

## 4. Verification

- [x] 4.1 Backend suggestion suites updated (prompt contract, zone stamping, clarification rarity).
- [x] 4.2 Vitest: prefill-on-edit, advanced collapse, tz prefill.
- [x] 4.3 Full backend + frontend suites green.
