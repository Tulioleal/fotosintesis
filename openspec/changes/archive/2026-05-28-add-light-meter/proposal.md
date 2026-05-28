## Why

Light conditions are a key care input, but browser sensor support varies. The MVP needs a resilient light measurement flow with sensor, camera and manual fallbacks.

## What Changes

- Implement AmbientLightSensor detection, permission request and lux reading when supported.
- Implement camera luminance fallback with approximate-measurement copy.
- Implement manual light registration fallback.
- Classify light as baja, media, alta or directa with reliability metadata.
- Detect unreliable camera measurements such as covered or overexposed image.
- Persist light measurements and optionally associate them to plants in Mi Jardin.

## Capabilities

### New Capabilities

- `light-meter`: light measurement by sensor, camera or manual input with classification and persistence.

### Modified Capabilities

- None.

## Impact

- Affects frontend permissions and measurement UI, backend light measurement persistence and garden/assistant context.
