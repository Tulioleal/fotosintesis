## 1. Reference And Baseline Review

- [x] 1.1 Review `frontend/REFERENCES/fotosintesis/DESIGN.md`, `frontend/REFERENCES/asistente_ai/screen.png`, and `frontend/REFERENCES/asistente_ai/code.html` before editing implementation files.
- [x] 1.2 Capture the target desktop visual verification state: plant context present, sidebar visible, at least one user message, at least one assistant message, and composer visible.
- [x] 1.3 Inspect current assistant behavior in `frontend/src/components/assistant/AssistantChat.tsx`, `frontend/src/components/assistant/AssistantChat.module.scss`, and `frontend/src/app/(private)/assistant/page.tsx` to preserve API, query, conversation, source, error, and reminder flows.

## 2. Assistant Layout Implementation

- [x] 2.1 Redesign the assistant page/component structure to support a desktop task-focused assistant layout with optional contextual plant sidebar, main chat area, scrollable thread, and anchored composer.
- [x] 2.2 Render the contextual plant sidebar only when plant context is available, showing display/nickname context, scientific or binomial context, and neutral placeholder treatments for unavailable image, location, or notes data.
- [x] 2.3 Provide the no-plant-context assistant state without a misleading empty sidebar while keeping the Fotosíntesis assistant visual language.
- [x] 2.4 Adapt visible reference product copy from `PlantCare` or other placeholders to `Fotosíntesis` or accurate current product copy.

## 3. Assistant Visual Styling

- [x] 3.1 Update `AssistantChat.module.scss` to use shared Fotosíntesis tokens for colors, typography, spacing, radii, surfaces, outlines, and elevation.
- [x] 3.2 Style assistant and user message rows with reference-like avatars/icons, labels, rounded bubble shapes, tonal fills, alignment, and raw-text whitespace preservation.
- [x] 3.3 Style the composer as a reference-like filled input/action area with accessible submit behavior and desktop anchored treatment.
- [x] 3.4 Add responsive mobile styling so the assistant remains usable inside the private shell with no horizontal overflow and no composer conflict with bottom navigation.
- [x] 3.5 Style pending and retryable error states with clear Fotosíntesis notice/error treatments while preserving duplicate-send prevention.

## 4. Sources And Reminder Suggestions

- [x] 4.1 Restyle structured source rendering as accessible Fotosíntesis source/supporting cards while preserving title/domain/URL fallback link behavior.
- [x] 4.2 Restyle assistant-origin reminder suggestion cards while preserving plant, action, due date/time, recurrence, and justification content.
- [x] 4.3 Preserve reminder suggestion acceptance payload mapping, disabled duplicate acceptance, accepted state, and failure state behavior.

## 5. Behavior Preservation Tests

- [x] 5.1 Update `AssistantChat.test.tsx` for any intentional copy/layout changes while preserving assertions for taxonomy query payload mapping and plant-only compatibility.
- [x] 5.2 Preserve or add component test coverage for conversation ID continuation after successful responses and retryable failures.
- [x] 5.3 Preserve or add component test coverage that markdown-labeled and unsupported assistant content formats render as raw text without parsing.
- [x] 5.4 Preserve or add component test coverage for retryable errors not appending assistant message bubbles.
- [x] 5.5 Preserve or add component test coverage for source link rendering and reminder suggestion acceptance states.
- [x] 5.6 Update relevant e2e assistant journey tests, if present, to verify the redesigned route keeps assistant entry links and query context valid.

## 6. Verification

- [x] 6.1 Run the frontend component test command covering `AssistantChat`.
- [x] 6.2 Run relevant assistant e2e journey tests or document why no applicable e2e command is available.
- [x] 6.3 Manually compare `/assistant` against `frontend/REFERENCES/asistente_ai/screen.png` using the same viewport class as the reference and the target plant-context verification state.
- [x] 6.4 Document any intentional visual deviations from the reference screenshot with the reason before marking implementation complete.
