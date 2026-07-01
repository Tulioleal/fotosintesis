## Why

The archived Fotosíntesis visual foundation now covers the primary shell, public/auth surfaces, identification, garden/profile, and assistant experiences, but the care tools still use older visual treatments. Redesigning reminders and the light meter now closes that gap while preserving the already-specified reminder and light measurement behavior.

## What Changes

- Redesign `/reminders` around the Fotosíntesis care-tool visual language, using `frontend/REFERENCES/recordatorios/screen.png` and `frontend/REFERENCES/recordatorios/code.html` as required visual references.
- Redesign `/light-meter` to align with the same care-tool family, deriving structure, cards, actions, status messaging, and save flows from the Fotosíntesis foundation and the already-redesigned plant detail/care-action surfaces.
- Define visual verification states for reminders and light meter before implementation, including realistic garden/reminder/suggestion/measurement content so dynamic data does not justify layout drift.
- Preserve existing reminders behavior, including list/create/update/complete/delete flows, recurring reminders, validation errors, notification permission messaging, and AI suggestion acceptance.
- Preserve existing light meter behavior, including sensor attempts, camera fallback, manual classification, reliability states, camera reliability blocking, garden plant association, and measurement persistence.
- Keep route behavior and existing links from garden, profile, assistant, and private shell surfaces valid.
- Keep user-facing product naming as `Fotosíntesis` and adapt any placeholder reference copy such as `PlantCare`.
- Preserve accessible labels, button names, form labels, and existing test expectations unless this change explicitly updates visible product copy or visual structure.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `frontend-visual-system`: Adds care-tool visual requirements and verification expectations for `/reminders` and `/light-meter` while preserving existing reminder and light-meter behavior specs.

## Impact

- Affected frontend routes and components: `src/app/(private)/reminders/page.tsx`, `src/app/(private)/light-meter/page.tsx`, `src/components/reminders/RemindersManager.tsx`, `src/components/light-meter/LightMeter.tsx`, and `src/components/light-meter/LightMeter.module.scss`.
- Shared care-tool, card, form, chip, notice, or action primitives may be reused or minimally extended if that keeps the implementation consistent with the Fotosíntesis foundation.
- Tests affected: reminders component tests, light-meter component tests, and relevant reminders/light-meter journey e2e tests.
- No backend API, database, reminder lifecycle, assistant suggestion, light measurement, or route contract changes are intended.
