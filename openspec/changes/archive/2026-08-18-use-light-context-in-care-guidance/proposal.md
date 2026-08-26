## Why

Light measurements are persisted with source, reliability, plant, and timestamp, and the assistant can query the latest measurement for a selected garden plant. But the current graph discards a found measurement instead of using it, and it queries light only for a narrow legacy intent rather than relevant care topics. Care guidance needs explicit, bounded use of recent reliable measurements.

## What Changes

- Let the multilingual classifier indicate whether light context is relevant.
- Apply relevance to watering, location, growth, stress, diagnosis, and recovery.
- Query only measurements associated with the selected garden plant.
- Add the accepted measurement to assistant state and answer context.
- Include value or classification, source, timestamp, age, and reliability.
- Add configurable freshness thresholds by supported measurement source.
- Exclude unreliable, stale, incompatible, or differently associated readings.
- Explain when a measurement influenced the recommendation.
- Explain limitations and suggest remeasurement when useful context is unavailable.
- Avoid measurement queries for requests where light cannot affect the answer.
- Make the same bounded context available to reminder suggestions.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `assistant-agent`: Load and apply relevant light context.
- `light-meter`: Define suitability of persisted readings for recommendation use.
- `assistant-reminder-suggestions`: Use light only when contextually justified.

## Impact

- Extend classifier and assistant-state schemas with bounded light context needs.
- Update graph nodes to retain repository results and pass them into synthesis.
- Add settings for freshness and reliability thresholds.
- Update prompt contracts to distinguish observation from botanical evidence.
- Add structured source metadata to assistant response details when applicable.
- Update reminder suggestion context integration.
