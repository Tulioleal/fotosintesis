## Context

`GardenList.tsx` hardcodes `const care = "Luz indirecta"` in every card and renders `"Último riego: Sin registros"` when a plant has no active reminders. `GardenDetail.tsx` renders a fixed `Luz Indirecta` chip and a reminder-count chip. None of these values are grounded in data: there is no watering-event model, and light state is only real when a persisted `light_measurements` row exists.

The backend already stores everything we need to show honest data:

- `reminders` rows carry `action`, `due_at` (UTC instant), `status`, and `timezone` (effective IANA zone from `correct-reminder-scheduling-integrity`).
- `light_measurements` rows carry `source` (`sensor`/`camera`/`manual`), `classification`, `reliability`, `lux`, and `measured_at`.
- `plant_profiles` carry evidence-backed `sections` (including `care` and `recommendations`) and a `confidence` value.

`GardenPlantResponse` is returned by both the list and detail endpoints and already embeds the full profile. This change adds two nullable summary fields and swaps the fake frontend labels for grounded rendering.

## Goals / Non-Goals

**Goals:**

- Stop presenting static care values as observed plant data.
- Surface the next pending reminder (action + timezone-aware due date) per plant.
- Label every displayed care value with its provenance (profile guidance vs measurement vs user input).
- Do this with additive schema changes and batched queries — no new tables or aggregation services.

**Non-Goals:**

- No watering-event tracking (no new tables or event model).
- No new reminder suggestion or notification delivery behavior.
- No long-term light trend analysis.
- No change to light-measurement eligibility thresholds (those govern recommendation use, not display).

## Decisions

### 1. Additive, nullable summary fields on the existing response

Add two nullable fields to `GardenPlantResponse`:

- `next_reminder: ReminderSummary | None` where `ReminderSummary = { id, action, due_at, timezone }`.
- `light_summary: LightSummary | None` where `LightSummary = { id, classification, lux, reliability, source, measured_at }`.

`active_reminders` stays in place: the backend delete-confirmation flow (`delete_garden_plant`) still reads it, and the home screen still uses it. The frontend simply stops rendering it as a count chip.

**Why:** Reuses existing rows; no migration; non-breaking. The summaries are lean (no full reminder/measurement DTO) because the list view only needs the next action and the latest reading.

**Alternative rejected:** A new `care_summary` table or aggregation service. Unnecessary — both sources already exist and are cheap to join at read time.

### 2. Batched next-reminder and light-summary selection

Both list and detail go through the repository, which resolves summaries with at most two extra queries per read using a `row_number()` window over `garden_plant_id`:

- Next reminder: `SELECT ... FROM (SELECT ..., row_number() OVER (PARTITION BY garden_plant_id ORDER BY due_at ASC) AS _row_number FROM reminders WHERE user_id = :uid AND status = 'pending') WHERE _row_number = 1`.
- Light summary: `SELECT ... FROM (SELECT ..., row_number() OVER (PARTITION BY garden_plant_id ORDER BY measured_at DESC) AS _row_number FROM light_measurements WHERE user_id = :uid AND garden_plant_id IS NOT NULL) WHERE _row_number = 1`.

The window approach was chosen over Postgres `DISTINCT ON` because the test backend runs on SQLite, where `DISTINCT ON` is unsupported and silently ignored; the window query yields identical per-plant selection on both backends without one query per plant.

Results are keyed into `{plant_id: summary}` maps and merged in `_garden_from_row`. The detail path reuses the same helpers scoped to a single plant id.

**Why:** Satisfies "no per-card reminder queries". `reminders.garden_plant_id` already has an index; a partial index on `(garden_plant_id, due_at) WHERE status = 'pending'` is optional and only added if the query plan warrants it.

**Alternative rejected:** A `/garden/{id}/next-reminder` endpoint would require one request per card (N+1) and more client orchestration.

### 3. Frontend renders grounded fields, not defaults

- `GardenList` card description becomes location-only; the meta line renders the next reminder ("{action} · {due date in timezone}") or an actionable "no pending care" state linking to the reminders page.
- `GardenDetail` replaces the "Luz Indirecta" chip with a grounded light chip from `light_summary` (classification + source label, "approximate" for camera) or a "Sin datos de luz" state; replaces the count chip with the next reminder action + due date.
- The existing "Medicion de Luz" readings list adds a per-reading source label and marks camera readings approximate in text.
- Profile guidance is rendered from `profile.sections.care` / `recommendations` and labeled "Recomendación del perfil" with `profile.confidence`, visually separate from user measurements so recommendations and observations are never collapsed.

Timezone rendering uses `Intl.DateTimeFormat` with `timeZone: next_reminder.timezone ?? Intl.DateTimeFormat().resolvedOptions().timeZone`.

**Why:** Keeps all display logic client-side and driven by nullable fields; no new backend endpoints for presentation.

### 4. Timezone fallback for legacy reminders

Reminders created before `correct-reminder-scheduling-integrity` may have a null `timezone`. Rendering falls back to the user's stored timezone, then the browser timezone. No instant is silently shifted.

## Risks / Trade-offs

- [Removing familiar labels makes cards sparse] → Provide actionable empty states (create-reminder link, light-meter CTA) instead of blank space.
- [Joined window queries could be slow at scale] → Bounded by a single user's garden; rely on the existing `garden_plant_id` index, and add the partial pending-reminder index only if profiling shows a need.
- [Latest light measurement may be stale] → This is intentionally a "latest" display summary, not an eligibility claim; eligibility thresholds remain owned by the recommendation path.
- [Profile and measurement values may disagree] → Present origins without merging; never reconcile claims in the UI.
- [Contract change breaks generated client] → Fields are additive; regenerate the OpenAPI TypeScript contract in the same change.
- [Existing tests encode the old fake values] → Replace `Balcón • Luz indirecta` and `Último riego` assertions deliberately with grounded assertions.
