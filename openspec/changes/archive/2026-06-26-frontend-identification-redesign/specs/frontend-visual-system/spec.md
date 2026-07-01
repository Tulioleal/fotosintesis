## ADDED Requirements

### Requirement: Identification journey applies Fotosíntesis foundation

The `/identify` journey SHALL apply the archived Fotosíntesis visual foundation across its initial, camera fallback, preview, analyzing, error, results, and confirmed-candidate states while preserving the existing identification behavior.

#### Scenario: Initial identification entry follows the reference
- **WHEN** an authenticated user opens `/identify` before selecting an image
- **THEN** the screen visually follows `frontend/REFERENCES/identificando_planta_2/screen.png` and `frontend/REFERENCES/identificando_planta_2/code.html` for the page heading, breathable botanical surface, rounded upload well, dashed media drop-zone treatment, primary upload/camera actions, and responsive spacing
- **AND** the screen uses the shared Fotosíntesis colors, typography, spacing, radii, surfaces, outlines, and elevation tokens

#### Scenario: Camera fallback remains available
- **WHEN** camera access is unavailable or permission is rejected
- **THEN** the journey shows the existing camera limitation notice and offers the existing file upload fallback
- **AND** the notice is styled with Fotosíntesis notice/error surfaces without changing the fallback behavior

#### Scenario: Preview uses the selected image
- **WHEN** the user selects or captures an image
- **THEN** the journey shows a rounded preview media area using the selected image with an accessible alt text
- **AND** the preview treatment follows the identification reference family rather than introducing unrelated imagery or colors

#### Scenario: Analyzing state follows the reference
- **WHEN** the selected image is being submitted to `/api/identifications`
- **THEN** the screen visually follows `frontend/REFERENCES/identificando_planta_1/screen.png` and `frontend/REFERENCES/identificando_planta_1/code.html` for muted image preview, scanning or progress treatment, analysis status text, and candidate skeleton rhythm
- **AND** the upload still uses the existing `/api/identifications` request flow

#### Scenario: Error state stays recoverable
- **WHEN** image upload or analysis fails
- **THEN** the journey presents the existing recoverable error message in a tokenized Fotosíntesis error or notice treatment
- **AND** the user can retry by using the existing upload or camera controls

#### Scenario: Results follow the reference
- **WHEN** identification candidates are returned
- **THEN** the screen visually follows `frontend/REFERENCES/resultados_de_identificaci_n/screen.png` and `frontend/REFERENCES/resultados_de_identificaci_n/code.html` for the captured-photo area, possible-match section heading, result count/status chip, rounded candidate cards, confidence treatment, trait content, and responsive one-column to multi-column layout
- **AND** each candidate still displays the current candidate name, scientific context, visible traits, confidence, GBIF validation status, and synonyms when present

#### Scenario: Confirmation safeguards are preserved
- **WHEN** a candidate is not GBIF validated
- **THEN** its confirmation action remains blocked
- **AND** the visual treatment communicates the unavailable validation state without enabling definitive profile, garden-save, or assistant flows

#### Scenario: Confirmed candidates keep navigation links
- **WHEN** a validated candidate is confirmed
- **THEN** the journey still renders valid links to the plant profile and assistant context for that candidate
- **AND** those links keep their current route behavior and accessible names unless explicitly updated by this spec

#### Scenario: Reference copy is adapted
- **WHEN** implementation adapts copy from identification references that mention `PlantCare`, generic static navigation, or unsupported placeholder behavior
- **THEN** visible user-facing copy uses `Fotosíntesis` and accurate current product messaging instead

#### Scenario: Existing test anchors remain stable
- **WHEN** unit or e2e tests interact with upload, camera, confirmation, profile, or assistant controls
- **THEN** the accessible labels, button names, link names, and route behavior used by the existing identification tests remain stable unless the test is intentionally updated for a spec-level copy change
