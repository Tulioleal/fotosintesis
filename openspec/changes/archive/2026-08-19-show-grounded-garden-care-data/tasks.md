## 1. Backend schema and contracts

- [x] 1.1 Add `ReminderSummary` and `LightSummary` models and nullable `next_reminder` / `light_summary` fields to `GardenPlantResponse` in `backend/app/profile_garden/schemas.py`
- [x] 1.2 Add batched `next_pending_reminder_summaries(user_id, plant_ids=None)` and `latest_light_summaries(user_id, plant_ids=None)` queries to `backend/app/profile_garden/repository.py` using `DISTINCT ON` (pending-only, earliest due / latest measured)
- [x] 1.3 Merge the summaries into `_garden_from_row` for both list and detail reads without per-plant queries
- [x] 1.4 Regenerate the OpenAPI TypeScript contract (`pnpm --filter frontend openapi:generate`)

## 2. Frontend rendering

- [x] 2.1 Update `GardenList.tsx` to drop the hardcoded light label and last-watering copy; render the next reminder (action + timezone-aware due date) or an actionable no-care state
- [x] 2.2 Add a timezone-aware date formatter helper (using `Intl.DateTimeFormat` with the reminder's effective timezone)
- [x] 2.3 Update `GardenDetail.tsx` to replace the fixed light and reminder-count chips with grounded `light_summary` and `next_reminder` rendering
- [x] 2.4 Label the existing light readings list with source (sensor/camera/manual) and mark camera readings approximate in text
- [x] 2.5 Render profile guidance from `profile.sections` labeled as profile recommendation with confidence, visually separate from user measurements

## 3. Tests

- [x] 3.1 Replace `GardenList.test.tsx` assertions on "Balcón • Luz indirecta" and "Último riego" with grounded next-reminder and no-care assertions
- [x] 3.2 Update `GardenDetail.test.tsx` to cover populated, no-data, and partial care states with source and approximation labels
- [x] 3.3 Add backend tests for batched next-reminder (earliest pending, completed/cancelled excluded) and latest light-summary selection
- [x] 3.4 Add accessibility assertions that approximation/confidence/no-data are exposed as text, not color alone

## 4. Verification

- [x] 4.1 Run backend lint and tests (`ruff check app/ tests/`, `pytest -x`)
- [x] 4.2 Run frontend lint and tests (`pnpm --filter frontend lint`, `pnpm --filter frontend test`)
- [x] 4.3 Run `openspec validate show-grounded-garden-care-data --strict`
