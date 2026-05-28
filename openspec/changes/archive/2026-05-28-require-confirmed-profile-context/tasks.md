## 1. Backend Enforcement

- [x] 1.1 Update `GET /plant-profiles/{scientific_name}` to require `get_current_user` and a required confirmed candidate ID query parameter.
- [x] 1.2 Add repository/service validation that loads the candidate for the current user, requires `validation_status == "validated"`, requires `confirmed_at` to be present, and rejects missing matches.
- [x] 1.3 Validate the requested scientific name against the candidate's accepted scientific name or suggested scientific name before profile retrieval/creation.
- [x] 1.4 Return appropriate HTTP errors for unauthenticated requests, missing candidate ID, unconfirmed/unvalidated candidates, wrong-user candidates, and name mismatches.

## 2. Frontend Integration

- [x] 2.1 Update the Next.js profile API route to resolve backend auth headers and forward them to the backend profile endpoint.
- [x] 2.2 Update `PlantProfileView` to include `confirmedCandidateId` in the profile fetch query and avoid requesting a profile when it is missing.
- [x] 2.3 Add or update UI copy for the missing/invalid candidate context state so users are directed to confirm a validated candidate first.
- [x] 2.4 Regenerate or update OpenAPI/client types if the endpoint signature is represented in generated artifacts.

## 3. Verification

- [x] 3.1 Add backend tests covering successful confirmed-candidate profile access and profile creation.
- [x] 3.2 Add backend tests covering unauthenticated, missing candidate ID, unconfirmed/unvalidated candidate, wrong-user candidate, and scientific-name mismatch failures.
- [x] 3.3 Add frontend route/component tests covering auth header forwarding and candidate ID inclusion in profile fetches.
- [x] 3.4 Run the relevant backend and frontend test suites for profile garden and identify/profile flows.
