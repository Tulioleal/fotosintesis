## Context

`GET /plant-profiles/{scientific_name}` currently creates or retrieves a profile using only the path name and optional locale query parameters. The identify UI already links to profiles only after a candidate is confirmed and includes `candidateId`, but `PlantProfileView` does not send that candidate ID to the profile API and the frontend proxy does not forward backend auth headers. The backend repository already has `_confirmed_candidate(candidate_id, user_id)` for garden saves, so the missing enforcement can be added without a new data model.

## Goals / Non-Goals

**Goals:**

- Make definitive profile retrieval/generation authenticated.
- Require a confirmed, validated candidate owned by the current user before returning a profile.
- Ensure the candidate's accepted or suggested scientific name matches the requested profile name.
- Reuse the existing server-side frontend backend-session boundary for profile API calls.
- Preserve existing RAG profile creation and alias selection behavior after authorization succeeds.

**Non-Goals:**

- Add public plant profile browsing by scientific name.
- Change identification confirmation semantics.
- Change garden save behavior except for sharing candidate validation logic where useful.
- Add new persistence tables or migrate existing profile data.

## Decisions

1. Require `candidateId` on profile requests instead of trusting the scientific name alone.

   Rationale: the confirmed candidate is the existing proof that a user chose a taxonomically validated plant. A bare scientific name cannot prove confirmation and would keep the endpoint effectively public.

   Alternative considered: allow authenticated users to request any validated scientific name. This was rejected because it does not satisfy the confirmed-candidate gate in the existing taxonomy requirement.

2. Enforce ownership and confirmation in the backend repository/service before profile creation.

   Rationale: the backend must own the security decision because client routing already tries to constrain access but can be bypassed. The existing `_confirmed_candidate` query checks validation status, confirmation timestamp, and user ownership and should be reused or promoted to a validation helper.

   Alternative considered: enforce only in the Next.js API route. This was rejected because direct backend API callers would still bypass the gate.

3. Validate requested name against the confirmed candidate's accepted scientific name, falling back to suggested name.

   Rationale: profile URLs include a scientific name, but the candidate ID is the authority. Name consistency prevents a valid confirmed candidate from authorizing unrelated profile creation.

   Alternative considered: ignore the path name and always serve the candidate's name. This was rejected because it hides mismatched URLs and can produce surprising cache/history behavior.

4. Forward backend auth headers from the profile frontend API route.

   Rationale: profile pages are private and should use the same server-only credential pattern as garden routes. Browser JavaScript continues to call the local Next.js API without reading backend session tokens.

   Alternative considered: call the backend directly from the client. This was rejected because it conflicts with the secure session boundary.

## Risks / Trade-offs

- Existing bookmarked `/profiles/{scientificName}` URLs without `candidateId` will stop loading profiles -> show a clear message directing users to confirm the plant from Identificar first.
- Previously created profile records may exist for unconfirmed names -> leave records in place but require authorization before returning them.
- Scientific-name normalization differences can cause false mismatches -> compare against accepted name first and suggested name fallback using the same values already persisted on candidates.
- API clients must update query parameters and auth handling -> reflect the new required candidate ID in OpenAPI/types/tests.

## Migration Plan

1. Update backend endpoint and repository validation to require auth and `candidate_id`.
2. Update frontend profile proxy to require a backend session and forward auth headers.
3. Update `PlantProfileView` to include `candidateId` when fetching the profile and handle missing candidate ID as a gated state.
4. Update OpenAPI-generated types if project workflow requires generated client freshness.
5. Deploy as a behavior-tightening change; rollback is reverting endpoint signature/proxy changes if needed.
