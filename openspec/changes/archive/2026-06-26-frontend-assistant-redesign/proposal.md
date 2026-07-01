## Why

The assistant experience still needs the archived Fotosíntesis visual system applied so it feels coherent with the redesigned private shell, garden/profile, identification, and auth surfaces. This change brings the assistant chat into the same botanical editorial language while preserving the existing assistant API, conversation flow, plant context, source rendering, reminder suggestions, and raw-text message behavior.

## What Changes

- Redesign `/assistant` around the Fotosíntesis assistant reference in `frontend/REFERENCES/asistente_ai/screen.png` and `frontend/REFERENCES/asistente_ai/code.html`.
- Add a desktop assistant layout with a task-focused header treatment, contextual plant sidebar when plant context is available, main chat stream, and fixed or anchored composer.
- Add a mobile assistant layout that remains usable inside the existing private shell and avoids conflicts with bottom navigation.
- Restyle assistant message bubbles, pending state, retryable error state, source cards, reminder suggestion cards, and composer using the archived Fotosíntesis visual tokens.
- Preserve `/api/assistant/chat` behavior, conversation ID handling, plant query parameter context, binomial/scientific-name payload mapping, retryable errors, sources, and reminder suggestion acceptance.
- Preserve current assistant message rendering as raw text without markdown parsing.
- Replace any reference placeholder product copy such as `PlantCare` with user-facing `Fotosíntesis` copy.
- Define a required visual verification state for implementation using a plant-context assistant session that approximates the reference screenshot.
- Avoid redesigning reminders, light-meter, garden detail, or plant profile screens beyond keeping assistant entry links and query context valid.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `frontend-visual-system`: Add assistant-specific visual requirements for applying the archived Fotosíntesis system to the chat layout, contextual sidebar, messages, composer, and visual verification state.
- `assistant-agent`: Add frontend chat presentation requirements that preserve existing assistant behavior, route/query context, payload mapping, raw-text rendering, sources, and retryable states while changing visual layout.
- `assistant-reminder-suggestions`: Add visual presentation requirements for assistant-origin reminder suggestion cards and acceptance states within the redesigned chat.

## Impact

- Affected frontend routes and components include `frontend/src/app/(private)/assistant/page.tsx`, `frontend/src/components/assistant/AssistantChat.tsx`, `frontend/src/components/assistant/AssistantChat.module.scss`, and `frontend/src/components/assistant/AssistantChat.test.tsx`.
- Shared UI primitives may be used or minimally extended for assistant messages, source cards, reminder suggestion cards, and contextual sidebars if needed.
- Relevant e2e assistant journey tests may need updates to cover preserved behavior in the redesigned layout.
- No backend API contract or dependency changes are expected.
