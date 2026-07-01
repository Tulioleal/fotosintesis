## Context

The archived Fotosíntesis visual foundation is already the baseline for the redesigned private shell, public/auth surfaces, identification flow, and garden/profile surfaces. The assistant currently preserves the required functional behavior but uses an older card-based layout that does not match the dedicated assistant reference in `frontend/REFERENCES/asistente_ai/screen.png` and `frontend/REFERENCES/asistente_ai/code.html`.

The current assistant component reads `plant`, `binomial`, and `scientific` query parameters, sends them to `/api/assistant/chat` as `plant`, `plant_binomial_name`, and `plant_scientific_name`, preserves conversation IDs, renders retryable errors without appending assistant messages, renders sources from `sources[]`, and accepts assistant-origin reminder suggestions through the reminders API. It also intentionally renders assistant message content as raw text, including future or markdown content formats.

The reference layout is desktop-first: a task-focused top treatment, a 320px contextual plant sidebar, a main chat stream, assistant/user bubbles, and a bottom anchored composer. Mobile must adapt this structure inside the existing private shell without overlapping bottom navigation.

Target visual verification state before implementation:

- Viewport class: desktop width matching the reference screenshot class, using the same browser/device class selected for `frontend/REFERENCES/asistente_ai/screen.png` comparison.
- Route/state: `/assistant?plant=Monty&binomial=Monstera%20deliciosa&scientific=Monstera%20deliciosa` or equivalent mocked/test state with plant context present.
- Sidebar content: visible plant-context panel with display name or nickname, scientific/binomial name, and location/notes placeholders only when live data is unavailable.
- Conversation content: at least one user message about a plant-care issue, at least one assistant response, and the composer visible.
- Optional contextual content: source cards and/or a reminder suggestion card may be present for behavior verification, but layout fidelity must not depend on dynamic API text.
- Verification rule: dynamic data differences cannot justify layout drift; mocked data should approximate the reference where needed.

Intentional reference adaptations:

- Replace `PlantCare` with `Fotosíntesis` in visible product copy.
- Keep the existing private shell navigation instead of duplicating unsupported header actions from the static reference when those actions conflict with the live app shell.
- Keep assistant prose raw-text rendering, so any bullet-like model output remains plain text rather than parsed HTML lists.

## Goals / Non-Goals

**Goals:**

- Apply the archived Fotosíntesis tokens, typography, surfaces, outlines, radii, and icon strategy to the assistant experience.
- Match the reference structure, spacing, typography, color, card/message shape, and hierarchy at the defined desktop visual verification state.
- Provide a responsive mobile layout that keeps the composer usable and clear of private-shell bottom navigation.
- Preserve all existing assistant chat behavior, including API endpoint, payload mapping, conversation ID handling, retryable errors, sources, reminder suggestion acceptance, and raw-text message rendering.
- Preserve accessible labels, button names, and route behavior unless a spec explicitly changes copy.

**Non-Goals:**

- No backend assistant behavior changes.
- No markdown parsing or rich rendering for assistant messages.
- No redesign of reminders, light-meter, garden detail, or plant profile screens beyond preserving valid assistant entry links and query context.
- No new semantic plant-care classification, retrieval, or answerability behavior.
- No new deterministic keyword or language heuristics for botanical meaning.

## Decisions

### Decision: Redesign within the existing assistant component boundary

Implement the layout primarily in `AssistantChat.tsx` and `AssistantChat.module.scss`, with small shared primitive use or extraction only if it reduces duplication for message bubbles, source cards, reminder suggestion cards, or the plant sidebar.

Rationale: The change is visual and presentational while current behavior is already concentrated in `AssistantChat`. Keeping state and API calls in place lowers regression risk.

Alternative considered: Split the entire assistant into a page-level layout controller plus multiple subcomponents before redesigning. This would add more names and boundaries without a functional need.

### Decision: Use the query-provided plant context as the guaranteed sidebar source

The sidebar should render when plant context is available from query parameters. It should show the display name/nickname from `plant`, scientific/binomial context from `binomial` or `scientific`, and only use neutral location/notes placeholders when richer garden data is not available in the current assistant route.

Rationale: The requested implementation must preserve existing route and payload behavior. Fetching new garden detail data from the assistant page would add API dependency and ambiguity not required for this change.

Alternative considered: Add a garden plant lookup for location and notes. This may be useful later, but it would expand scope and risk changing assistant loading/error behavior.

### Decision: Keep raw text rendering in a visually styled message shell

Assistant messages should keep using `AssistantMessageContent` with `white-space: pre-wrap` and no markdown parser. The redesign changes the bubble, label, avatar/icon, and spacing, not content interpretation.

Rationale: Current tests and product behavior explicitly require markdown-like content to remain raw text until a separate spec changes it.

Alternative considered: Match the reference HTML list rendering by parsing markdown. This is explicitly out of scope and would change behavior.

### Decision: Anchor the composer within the assistant chat area with mobile safe spacing

On desktop, the composer should be visually anchored to the bottom of the chat area similar to the reference. On mobile, it should remain in normal or sticky flow with enough bottom padding to avoid conflict with the private shell bottom navigation.

Rationale: The reference expects an always-available composer, but the app shell already owns mobile navigation. The assistant layout must not create overlapping fixed controls.

Alternative considered: Use a viewport-fixed composer on all breakpoints. This matches the static reference more closely but risks covering bottom navigation and content on mobile.

### Decision: Preserve source and reminder behavior while restyling them as supporting cards

Sources should remain links from `sources[]` and reminder suggestions should keep existing acceptance logic and button names. Visual styling can move them near related assistant responses or into a support rail/stack as long as accessible names and behavior remain intact.

Rationale: The API and tests depend on these behaviors. Styling should not weaken source attribution or reminder confirmation safeguards.

Alternative considered: Hide sources behind a disclosure by default. This may reduce visual clutter but would make existing source rendering less direct.

## Risks / Trade-offs

- [Risk] The private shell header/bottom navigation may constrain exact screenshot fidelity. → Mitigation: document any shell-driven deviations in implementation verification notes and keep the assistant internal structure faithful to the reference.
- [Risk] Anchored composer behavior can overlap content on small screens. → Mitigation: use breakpoint-specific layout and bottom safe spacing tied to the shell navigation height.
- [Risk] Query-only plant context may not provide image, location, or notes from the static reference. → Mitigation: preserve the sidebar structure and use live-safe placeholders only where data is unavailable, without inventing plant facts.
- [Risk] Visual changes may break tests that query current placeholder or context copy. → Mitigation: preserve button accessible names and only update text expectations when the spec requires new product naming or layout copy.
- [Risk] Source and reminder cards may drift from reference if dynamic content is sparse. → Mitigation: use mocked/test data approximating the reference for visual verification and do not use dynamic text differences to justify spacing or hierarchy drift.

## Migration Plan

- Implement behind the existing `/assistant` route and component; no data migration is required.
- Run component tests for `AssistantChat` and relevant assistant journey e2e tests.
- Perform manual visual comparison against `frontend/REFERENCES/asistente_ai/screen.png` using the defined desktop plant-context state and viewport class.
- Rollback strategy: revert the frontend route/component/style changes; no persisted data or backend contract changes are introduced.

## Open Questions

- None currently blocking implementation. Any unavailable plant image, location, or notes should be treated as live-data limitations and represented with neutral placeholder/sidebar treatments rather than new data fetching.
