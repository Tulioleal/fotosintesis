## Why

Plant identification is the main entry point for the app, but MaaS visual results are uncertain. The MVP needs a safe flow that treats image analysis as assisted candidates and validates taxonomy before downstream use.

## What Changes

- Implement image capture/upload UI with camera permission handling and upload fallback.
- Implement backend image receipt, validation, metadata persistence and object storage write.
- Implement MaaS multimodal candidate identification through the vision provider interface.
- Display up to 3 candidates with visible traits, qualitative confidence and possible-match copy.
- Integrate GBIF Species API for scientific name validation and normalization.
- Persist GBIF identifiers, accepted names, synonyms, genus, family and species metadata.
- Block definitive profile generation, garden save and reminders until user confirms a validated candidate.
- Implement low-confidence, no-plant, blurry-image, MaaS-unavailable and no-GBIF-match sad paths.

## Capabilities

### New Capabilities

- `plant-identification-taxonomy`: assisted visual identification, GBIF validation and confirmation gating.

### Modified Capabilities

- None.

## Impact

- Affects camera/upload UI, backend image ingestion, object storage, vision provider usage, GBIF integration and candidate confirmation state.
