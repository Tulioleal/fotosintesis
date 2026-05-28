## Why

After a plant is confirmed, users need an evidence-backed profile and a way to manage their own plants. This change turns validated plant knowledge into user-facing profiles and Mi Jardin records.

## What Changes

- Implement plant profile generation/retrieval using RAG evidence.
- Render profile sections for names, alias, scientific name, description, characteristics, conditions, care, pests, diseases and recommendations.
- Implement alias regional fallback by region, country or language without exact GPS.
- Show sources, confidence and limitation messages.
- Add profile CTAs for Mi Jardin, assistant, reminder and light measurement flows.
- Implement garden save for confirmed plants with optional image and user customization.
- Implement Mi Jardin list, search, detail and empty state.
- Implement garden plant deletion with explicit confirmation when active reminders exist.

## Capabilities

### New Capabilities

- `plant-profile-garden`: RAG-backed plant profiles and Mi Jardin management.

### Modified Capabilities

- None.

## Impact

- Affects profile APIs/UI, garden persistence, user plant customization, source display and cross-feature CTAs.
