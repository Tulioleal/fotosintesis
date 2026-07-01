# Verification Notes — Frontend Care Tools Redesign

## Verification status

| Task | Status | Evidence |
|------|--------|----------|
| 5.1 Update reminders component tests | done | `src/components/reminders/RemindersManager.test.tsx` (9/9 pass, includes the new "falls back to 'Revisión general'" test) |
| 5.2 Update light-meter component tests | done | `src/components/light-meter/LightMeter.test.tsx` (2/2 pass; existing tests already aligned with new structure) |
| 5.3 Run component tests | done | `pnpm --filter frontend test` → 108/108 pass across 25 files (2026-06-29) |
| 5.4 Run e2e journey tests | done | New deterministic `e2e/care-tools.spec.ts` covers the care-tools paths without depending on vision/LLM providers. 4/4 pass against the local Docker stack (PostgreSQL + backend on `:8000` + frontend on `:3000`). Seed setup runs in `e2e/care-tools.setup.ts` via `e2e/seed_care_state.py` (registers a user through the public API and inserts the plant + reminders + measurements directly into the database, bypassing the identify flow). See "Deterministic care-tools E2E" below. |
| 5.5 Manual visual compare `/reminders` vs reference | done | Authenticated screenshots captured at 1440x900 and 390x844 against the deterministic seeded state (one plant "Pothos del living" in Mi Jardín + reminders: "Riego" weekly and "Fertilizante" monthly; an additional "Fertilizante" reminder created by the e2e for verification). The desktop screenshot now shows the row action trigger (`MoreVertIcon` button) visible by default on every row — no hover required. See `verification/reminders-1440x900.png` and `verification/reminders-390x844.png`. |
| 5.6 Manual visual verify `/light-meter` | done | Authenticated screenshots captured at 1440x900 and 390x844 with a prepared manual "Alta" reading (via the deterministic `Usar registro manual` path, which avoids the sensor/camera paths and external model providers). The result card shows the `REGISTRO MANUAL` + `CONFIABILIDAD BAJA` chips, the `Luz alta` heading, and the save card with optional plant association is visible. See `verification/light-meter-1440x900.png` and `verification/light-meter-390x844.png`. |

### Deterministic care-tools E2E (2026-06-29)

`pnpm --filter frontend test:e2e -- e2e/care-tools.spec.ts` exercises the care-tools flows with a deterministic seed (no external vision/LLM providers required). 4/4 pass.

- Setup (`e2e/care-tools.setup.ts`): runs `e2e/seed_care_state.py` once before the suite to register a user via the public API and insert a plant + two reminders + one light measurement directly into the database. The credentials are written to a JSON file the tests read.
- Test 1 — `/reminders` loads seeded state: confirms the page renders with the seeded plant pre-selected in the form, the `2 activos` chip is present, and both seeded reminders (`Riego`, `Fertilizante`) appear in the list.
- Test 2 — Row action affordance: confirms the per-row `MoreVertIcon` trigger is visible by default (`getComputedStyle(trigger).opacity > 0.9`) and clicking it opens a menu with `Editar` / `Completar` / `Eliminar` items.
- Test 3 — Create reminder via form: fills `Tipo de Tarea=Fertilizante`, `Fecha=2999-01-20`, `Hora=10:30`, clicks `Guardar recordatorio`, and asserts `Recordatorio guardado.` notice plus the `3 activos` chip.
- Test 4 — Light-meter manual reading: selects `Alta` in `Condicion observada`, clicks `Usar registro manual`, asserts the `Luz alta` result heading, clicks `Guardar medicion`, and asserts the `Medicion guardada correctamente.` notice.

The pre-existing `mvp-journeys.spec.ts` tests (1 pass / 3 provider-dependent failures) remain unchanged and continue to be the broader-MVP journey suite; the new `care-tools.spec.ts` is the care-tool-specific evidence. The pre-existing `beforeEach` register→login race fix in `mvp-journeys.spec.ts` is unrelated to the care-tools scope and stays.

## Visual verification state (achieved)

### Reminders (`/reminders`)

- **Seeded state:** user with one confirmed plant ("Pothos del living" — `Epipremnum aureum`, `Epipremnum aureum` profile) and two pending reminders: `Riego` (weekly) and `Fertilizante` (monthly), each with a `suggestion_justification` populated.
- **Desktop (1440x900):** private shell top bar with brand + desktop nav (Home, Identificar, Mi Jardín, Luz, **Recordatorios** active, Asistente) + logout. Page eyebrow "CUIDADOS" + H1 "Recordatorios". Left column renders the `Nuevo Recordatorio` form (Planta select showing the seeded plant, `Tipo de Tarea` select, Fecha, Hora, Frecuencia chip group with `Personalizado` active, `GUARDAR RECORDATORIO` primary) followed by the tonal `Sugerencias con IA` card with the `Generar con IA` action. Right column renders `Lista de Recordatorios Actuales` with the `2 activos` chip and the PLANTA / TAREA / PRÓXIMA FECHA / ACCIÓN table-style header over two rows (each showing the `PotIcon` avatar, plant name, neutral `BellIcon` + action label, due date, recurrence, suggestion justification). Footer renders the brand + copyright line aligned with the shell.
- **Mobile (390x844):** form, AI card, and list stack vertically inside the private shell. Field `*` markers remain aria-hidden but visible. Bottom nav overlays as expected; the list rows collapse to a stacked layout (primary + secondary).
- **Visual rules confirmed:** the neutral `BellIcon` is the single task icon (no keyword classification). The action label next to it carries the vocabulary value (`Riego | Fertilizante | Poda | Trasplante | Limpieza | Revisión general`) for that reminder. The action is constrained to this vocabulary on the form (`Tipo de Tarea` select), on the local AI suggestion builder, and on the assistant's reminder-suggestion acceptance path, so every reminder saved through the UI is representable in the form on edit. The reference `PlantCare` copy is replaced with `Fotosíntesis`. No new top bar, bottom nav, or fixed nav is added inside the page. Custom SVG icons match the rest of the Fotosíntesis surfaces.

### Light meter (`/light-meter`)

- **Seeded state:** same user (the manual reading is created in-page via the deterministic `Usar registro manual` flow; the seeded `light_measurements` row is for context and is not required for the rendered page state).
- **Desktop (1440x900):** PageHeader `CUIDADOS` / `Medidor de luz` + description, intro line, status Notice, two-column layout. Left primary column: `Medicion principal` card (sensor status list: sensor no disponible / cámara lista para usar / cámara inactiva; primary `Medir luz` + outline `Usar camara` actions) and the `Luz alta` result card with `REGISTRO MANUAL` + `CONFIABILIDAD BAJA` chips, heading, lux copy, and manual copy. Right aside: `Registro manual` card (Condicion observada select on `Alta`, `Usar registro manual` secondary action) and `Guardar medicion` card (optional plant select including the seeded `Pothos del living` once seeded, `Guardar medicion` primary action).
- **Mobile (390x844):** cards stack vertically; primary measure + result + manual + save are all reachable, no horizontal overflow, bottom nav overlays as expected.
- **Visual rules confirmed:** measurement-first ordering kept; sensor/camera status list visible; reliability and source surfaced as tonal chips; save button visible and eligible (low-reliability manual reading is savable; only `low + camera` is gated, unchanged from existing behavior).

## Intentional visual deviations from `frontend/REFERENCES/recordatorios/screen.png`

1. **Brand copy** — the reference uses `PlantCare`; the implementation uses `Fotosíntesis` (per design.md and product naming). The static reference footer, "PlantCare" header logo, and `© 2024 PlantCare Botanical Systems` line are not exposed; the live private shell provides the real header, bottom navigation, and footer.
2. **Top header / static navigation** — the reference renders a custom top app bar with brand and notifications/account icons inside the screen. The implementation relies on the existing private shell `AppShell` top bar (with desktop nav, brand link, and logout) plus the bottom navigation on mobile. Avoiding duplication keeps behavior consistent with the rest of the authenticated experience.
3. **Bottom nav** — the reference renders a fixed bottom nav inside the screen. The implementation relies on the existing private shell bottom navigation (which already covers the same destinations). No new fixed nav is added inside the page.
4. **Material Symbols icons** — the reference uses Material Symbols (notifications, account_circle, water_drop, science, more_vert). The implementation uses the project's custom SVG icon set (`BellIcon`, `DropletIcon`, `SparkleIcon`, `SunIcon`, `PotIcon`, `CameraIcon`) to stay consistent with the rest of the Fotosíntesis surfaces.
5. **Plant avatar imagery** — the reference shows external Google-hosted plant photos in each row. The implementation uses a `PotIcon` in a tonal square avatar (no remote image dependency, consistent with garden/profile). The product does not yet expose a stable plant image URL in the reminder API.
6. **AI suggestions affordance** — the reference shows a single "Generar con IA" CTA. The implementation renders a list of generated suggestions (per the existing suggestion builder) with one "Aceptar sugerencia" action each, because the product's suggestion flow is a list, not a generator dialog.
7. **Status messaging** — the original code rendered "Cargando recordatorios..." as a visible paragraph while the list loaded. The implementation renders skeleton rows visually and keeps the same text as a screen-reader-only status to preserve the existing test anchor and the WCAG-style live region pattern, without showing placeholder copy inside the visual hierarchy.
8. **Field required marker** — `Field` and `SelectField` render a `*` after the label for required fields. The reference shows clean labels. The marker is `aria-hidden="true"`, so the accessible name remains the label text, but a visible `*` is part of the shared primitive and benefits the form's perceived affordance.
9. **Density on mobile** — on screens < 720px the right-column list collapses to a stacked layout (primary + secondary per row) instead of forcing the 12-column grid. The reference does not have a verified mobile screenshot, so we keep the desktop comparison anchor and ensure stacked, readable rows on small screens.
10. **Reminder action vocabulary** — the form exposes six fixed `Tipo de Tarea` values (`Riego | Fertilizante | Poda | Trasplante | Limpieza | Revisión general`) and both AI suggestion paths normalize to that vocabulary (local builder maps the plant's care plan keywords; assistant-side path maps the LLM's free-text action). The pre-redesign form accepted arbitrary free-text action labels; the redesigned form intentionally constrains them so the action is always representable on edit and rows carry a consistent visual language. The backend schema still accepts any non-empty string for backwards compatibility with reminders created before the redesign; only the UI paths are constrained.

## Intentional visual deviations from the derived light-meter care-tool pattern

1. **No screenshot reference** — the light meter has no reference image, so the visual is derived from the Fotosíntesis foundation, the already-redesigned plant detail/care-action surfaces, and the reminders split layout. The "measurement-first" decision is documented in `design.md`.
2. **Action order** — the reference reminds the user to "Medir luz" first; the implementation surfaces both the auto-measure primary action and the manual "Usar registro manual" form on the same screen, because the existing behavior keeps both available and we do not want to hide the manual fallback.
3. **Sensor/camera status list** — added a small status list (sensor / camera / camera-active) inside the primary measurement card to make fallback availability explicit during verification, without changing measurement behavior.
4. **Save eligibility chip** — the result card surfaces reliability and source as tonal chips, replacing the original inline `confiabilidad X` text. Save eligibility rules (no reading, saving, low-reliability camera) are unchanged.

## Cross-feature link integrity

- Bottom navigation links to `/reminders` and `/light-meter` remain valid (`src/components/layout/BottomNavigation.tsx`).
- `PlantProfileView` and `GardenDetail` continue to link to `/reminders?plant=...` and `/light-meter?plant=...` with the same href pattern; the `?plant=` hint is still consumed by `RemindersManager` via `useSearchParams` and ignored by `LightMeter` (no behavior change).
- Middleware matcher and protected routes are unchanged.
- No other route, profile, garden, assistant, identification, or public/auth surface was modified.

## Completed follow-ups

1. `pnpm --filter frontend test:e2e` was run against the local Docker stack on 2026-06-29. The reminder-creation journey in `mvp-journeys.spec.ts` is deterministic after the `beforeEach` race fix; the remaining 3 failures are documented as a carve-out above (vision/LLM provider dependency, outside this change's scope).
2. A new deterministic `e2e/care-tools.spec.ts` was added with `e2e/care-tools.setup.ts` (globalSetup) and `e2e/seed_care_state.py` (DB seeder). 4/4 pass and exercise the `/reminders` loaded state, the row action affordance, the create-reminder form, and the `/light-meter` manual reading + save. This replaces the previous carve-out as the care-tools e2e evidence.
3. Authenticated browser screenshots of `/reminders` and `/light-meter` were re-captured at 1440x900 desktop and 390x844 mobile viewports on 2026-06-29 against the seeded state described above. The desktop `reminders-1440x900.png` now shows the row action trigger (`MoreVertIcon`) visible on every row by default — discoverability no longer depends on hover. Files:
   - `verification/reminders-1440x900.png`
   - `verification/reminders-390x844.png`
   - `verification/light-meter-1440x900.png`
   - `verification/light-meter-390x844.png`
4. Unused shared UI additions from the keyword-based icon vocabulary (removed earlier in this change) were confirmed unused and removed: `WaterDropIcon`, `ScienceIcon`, `ContentCutIcon`, `YardIcon`, `CleaningServicesIcon`, `FieldVariant` type, and the `variant="underline"` style block. `MoreVertIcon` (used by reminder row actions) was kept.

## Open follow-ups

None.

