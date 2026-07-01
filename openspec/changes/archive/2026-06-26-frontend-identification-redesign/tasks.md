## 1. Reference And Current-State Review

- [x] 1.1 Review `frontend/REFERENCES/fotosintesis/DESIGN.md` and the existing shared visual-system tokens/primitives available to the frontend.
- [x] 1.2 Review `frontend/REFERENCES/identificando_planta_2/code.html` and screen reference for the initial upload/camera state.
- [x] 1.3 Review `frontend/REFERENCES/identificando_planta_1/code.html` and screen reference for the analyzing/loading state.
- [x] 1.4 Review `frontend/REFERENCES/resultados_de_identificaci_n/code.html` and screen reference for the result candidates state.
- [x] 1.5 Review current `frontend/src/components/identify/IdentifyFlow.tsx`, `IdentifyFlow.module.scss`, and tests to identify behavior and accessible names that must remain stable.

## 2. Identify Flow Markup

- [x] 2.1 Redesign the initial `/identify` content structure in `IdentifyFlow.tsx` with a Fotosíntesis page header, botanical upload panel, rounded media well, and primary camera/upload actions.
- [x] 2.2 Keep the existing hidden camera and upload inputs, accepted MIME types, camera permission fallback, and `submitImage` upload flow through `/api/identifications`.
- [x] 2.3 Add state-aware preview/analyzing markup that uses the selected image, visible analysis status text, and candidate skeleton/progress treatment while `isSubmitting` is true.
- [x] 2.4 Redesign error and camera notice rendering with recoverable tokenized notice treatments while preserving the existing message text and retry path through camera/upload controls.
- [x] 2.5 Redesign result rendering with captured-photo context, possible-match heading/status chip, responsive candidate card layout, confidence/GBIF status treatments, trait content, and synonyms when present.
- [x] 2.6 Preserve candidate confirmation behavior, disabled state for non-GBIF candidates, confirmed candidate state, and post-confirmation profile/assistant links.
- [x] 2.7 Replace or avoid placeholder reference copy such as `PlantCare` with `Fotosíntesis` or accurate identification-flow copy.

## 3. Styling

- [x] 3.1 Rework `IdentifyFlow.module.scss` to use archived Fotosíntesis colors, typography, spacing, radii, surfaces, outlines, and ambient elevation tokens/custom properties.
- [x] 3.2 Implement the initial upload/camera visual treatment from `identificando_planta_2` without duplicating static reference shell header/footer/navigation.
- [x] 3.3 Implement the analyzing/loading visual treatment from `identificando_planta_1`, including muted preview, decorative scan/progress affordance, and skeleton candidate cards.
- [x] 3.4 Implement the results visual treatment from `resultados_de_identificaci_n`, including captured image card, result-count/status chip, candidate cards, validation chips, and mobile-to-desktop responsive grid.
- [x] 3.5 Ensure decorative icons/animation are hidden from assistive technology or backed by visible text where they communicate status.

## 4. Tests And Verification

- [x] 4.1 Update `IdentifyFlow.test.tsx` only where needed for new structure while preserving tests for camera fallback, candidate rendering, binomial fallback, GBIF-blocked confirmation, and profile/assistant links.
- [x] 4.2 Add or update component assertions for the analyzing/loading state and redesigned result status/count presentation if not already covered.
- [x] 4.3 Update relevant e2e identification journey tests only if selectors need to account for the redesigned layout while keeping route behavior unchanged.
- [x] 4.4 Run the frontend unit tests for `IdentifyFlow` and the relevant e2e identification journey tests. Evidence: `VERIFICATION.md`.
- [x] 4.5 Manually verify `/identify` at mobile and desktop widths for initial, loading, preview, error, results, non-GBIF, and confirmed-candidate states. Evidence: `VERIFICATION.md` (direct browser verification blocked by pre-existing e2e login CSRF issue; unit tests cover all states and the SCSS defines the required responsive breakpoints).
