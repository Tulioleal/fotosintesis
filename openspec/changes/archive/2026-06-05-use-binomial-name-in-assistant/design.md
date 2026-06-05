## Context

The assistant chat API currently accepts `plant` as the selected plant context. That value is useful for display and backward compatibility, but it is not always the best operational value for search, structured plant-data APIs, or RAG acquisition because it can be a common name or a verbose full taxonomic name.

The identification flow can provide separate common/display, binomial, and accepted or suggested scientific names. Garden/profile views may also expose scientific context, and some profiles may expose a binomial name now or in a later backend/API shape. The assistant needs to preserve all useful context while selecting one deterministic plant name for retrieval and external data access.

## Goals / Non-Goals

**Goals:**

- Add optional `plant_binomial_name` and `plant_scientific_name` fields to assistant chat requests without breaking existing `plant`-only payloads.
- Centralize name selection so assistant graph/tool paths use the same operational and display/context priorities.
- Use the binomial name first for web search, structured plant-data APIs, RAG retrieval/acquisition, and trusted web fallback when it is available.
- Preserve full scientific name as taxonomic context for prompts, conversation state, and future disambiguation.
- Update frontend assistant links and chat payloads so the backend receives display, binomial, and scientific context from identification and garden/profile entry points.

**Non-Goals:**

- Add plant identification or disambiguation to structured plant-data providers.
- Change the public assistant route shape beyond optional query parameters and request fields.
- Require all garden/profile API responses to expose `binomial_name` in this change if they do not already do so.
- Migrate persisted conversations or existing plant profiles.

## Decisions

- Use two derived names in backend assistant handling: an operational plant name and a display/context plant name. The operational name uses `plant_binomial_name`, then `plant_scientific_name`, then `plant`; the display/context name uses `plant`, then `plant_scientific_name`, then `plant_binomial_name`. This keeps external lookup inputs stable while preserving current UX and compatibility.
- Keep `plant` as an optional request field. Removing or repurposing it would break existing clients and would conflate display labels with retrieval identifiers.
- Normalize empty strings to missing values before applying priority. This avoids sending blank query fragments to search/API/RAG tools when query parameters exist but are empty.
- Pass both derived names through assistant service/graph state rather than recomputing independently in each tool. A single selection point reduces priority drift across RAG retrieval, structured lookup, web fallback, and answer prompts.
- Frontend links should pass `plant`, `binomial`, and `scientific` query parameters where available. The chat component maps them to the backend request fields `plant`, `plant_binomial_name`, and `plant_scientific_name`.
- The assistant UI should show the display plant first and concise binomial context second when present. The full scientific name remains in the payload/context but is not shown by default if it is more verbose than the binomial.

## Risks / Trade-offs

- Name priority drift across assistant paths -> Mitigate by implementing shared helper/state fields and testing search/tool call inputs for each fallback case.
- Infraspecific names may still be needed by a provider or answer prompt -> Mitigate by preserving `plant_scientific_name` as taxonomic context even when operational lookup uses the binomial.
- Frontend routes may omit new query parameters from some entry points -> Mitigate by keeping backend fallback to existing `plant` and adding targeted link updates where data is available.
- Generated OpenAPI output may touch many files -> Mitigate by regenerating once after the backend schema change and reviewing generated/client diffs for only contract-related changes.
