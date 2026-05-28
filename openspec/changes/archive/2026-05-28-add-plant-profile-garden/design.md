## Context

This slice depends on confirmed taxonomy and the knowledge/RAG layer. It focuses on profile generation, source transparency and personal plant management.

## Goals / Non-Goals

**Goals:**

- Generate or retrieve profiles using RAG evidence.
- Render useful botanical and care sections with uncertainty messaging.
- Save confirmed plants to Mi Jardin with optional user customization.
- Provide list, search, detail, empty and deletion flows.

**Non-Goals:**

- No full assistant chat implementation.
- No reminder scheduling beyond CTAs and deletion awareness.
- No light measurement implementation beyond CTAs/context relationship.

## Decisions

- Profiles must expose sources and limitations where evidence is partial or dynamically acquired.
- Alias selection uses region, country or language and does not require exact GPS.
- Garden save requires user-confirmed validated species.
- Deleting a plant with active reminders requires explicit confirmation.

## Risks / Trade-offs

- Profiles can appear incomplete when evidence is weak; explicit limitation copy is preferred over hallucinated details.
- Cross-feature CTAs may point to not-yet-implemented flows during incremental development.
