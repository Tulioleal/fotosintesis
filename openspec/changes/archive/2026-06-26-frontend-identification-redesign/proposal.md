## Why

The identification journey still uses pre-foundation visuals while the Fotosíntesis design foundation, private shell/home, and public/auth surfaces have already been completed and archived. Redesigning `/identify` now brings the primary plant-identification flow into the same botanical visual system without changing its upload, camera, API, validation, or navigation behavior.

## What Changes

- Redesign the initial upload/camera entry state using `frontend/REFERENCES/identificando_planta_2/screen.png` and `frontend/REFERENCES/identificando_planta_2/code.html` as visual references.
- Redesign the analyzing/loading state using `frontend/REFERENCES/identificando_planta_1/screen.png` and `frontend/REFERENCES/identificando_planta_1/code.html` as visual references.
- Redesign the preview, error, result candidates, and confirmation actions so they follow the archived Fotosíntesis visual foundation and identification reference family.
- Preserve the existing upload and camera behavior, including the camera permission fallback to file upload.
- Preserve the existing identification API flow through `/api/identifications`.
- Preserve candidate confirmation safeguards, including blocking confirmation for candidates without GBIF validation.
- Preserve post-confirmation links to plant profile and assistant context.
- Keep user-facing product naming as `Fotosíntesis` and adapt placeholder reference copy such as `PlantCare` to accurate Fotosíntesis copy.
- Preserve accessible labels, button names, and route behavior used by tests unless the spec explicitly updates visible copy.
- Avoid redesigning garden, profile, or assistant screens beyond ensuring links from the identification flow remain valid.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `frontend-visual-system`: extend the archived Fotosíntesis visual-system requirements to cover the plant identification journey states.

## Impact

- Affected frontend files include `frontend/src/app/(private)/identify/page.tsx`, `frontend/src/components/identify/IdentifyFlow.tsx`, and `frontend/src/components/identify/IdentifyFlow.module.scss`.
- Affected tests include `frontend/src/components/identify/IdentifyFlow.test.tsx` and `frontend/e2e/mvp-journeys.spec.ts` for the identification journey.
- The `/api/identifications` API contract, upload/camera flow, GBIF validation gate, and post-confirmation profile/assistant routes remain behaviorally unchanged.
- No new dependencies or backend changes are expected.
- Verification evidence is recorded in `VERIFICATION.md` alongside this proposal.
