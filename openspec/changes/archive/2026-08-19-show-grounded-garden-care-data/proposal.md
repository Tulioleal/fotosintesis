## Why

Garden cards and details display fixed, evidence-free care values: every card shows a hardcoded "Luz indirecta" label and a "Último riego: Sin registros" fallback even though no watering-event model exists. These static defaults read as observed plant data when they are not. Garden views should show only sourced recommendations, real measurements, or user data, and should surface the next real care action instead of a reminder count.

## What Changes

- Remove the hardcoded indirect-light label from garden cards and details.
- Remove the last-watering copy until watering events are actually recorded.
- Show a `No data` state when no supported care datum is available.
- Distinguish profile recommendations from user measurements and manual values.
- Include source type, observation date, and reliability or approximation where applicable.
- Add the next pending reminder to each garden card.
- Show the reminder action and its timezone-aware due date rather than only a count.
- Preserve access to the complete reminder list from garden detail.
- Keep loading, empty, error, retry, and partial-data states accessible.
- Communicate confidence and missing data with text, not color alone.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `plant-profile-garden`: Grounded garden care summaries (nullable next-reminder and light summaries) and care-value provenance.
- `garden-query-data-fetching`: Query and render provenance-aware garden care fields and their states.
- `reminders`: Expose the next pending reminder efficiently for garden reads.

## Impact

- Extend `GardenPlantResponse` with nullable `next_reminder` and `light_summary` fields.
- Add batched repository queries for next pending reminders and latest light measurements.
- Update generated OpenAPI TypeScript contracts.
- Update `GardenList` and `GardenDetail` rendering and styles.
- Replace tests that assert fixed indirect-light and last-watering text.
- Add provenance, no-data, timezone, and accessibility coverage.
