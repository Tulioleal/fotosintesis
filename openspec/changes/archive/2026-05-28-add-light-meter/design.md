## Context

This slice implements an environmental input that can improve plant-care recommendations. It must degrade gracefully because AmbientLightSensor is not widely available.

## Goals / Non-Goals

**Goals:**

- Prefer real lux readings when AmbientLightSensor is available.
- Provide camera luminance estimation as an approximate fallback.
- Provide manual light registration as a final fallback.
- Persist measurements with reliability metadata and optional plant association.

**Non-Goals:**

- No guarantee of lab-grade lux accuracy.
- No hardware-specific native sensor integration beyond browser APIs.

## Decisions

- Measurement priority is AmbientLightSensor, camera luminance, then manual registration.
- Camera measurements are explicitly labeled approximate.
- Covered, overexposed or inconsistent readings are marked unreliable.
- Classifications use baja, media, alta and directa to match Spanish product copy.

## Risks / Trade-offs

- Camera estimation can be inaccurate; reliability metadata and copy must make this clear.
- Permission prompts can fail; manual registration keeps the flow usable.
