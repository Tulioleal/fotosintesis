# Visual Verification Notes

## Environment

- **Viewport (desktop):** 1440 x 900 (matches the desktop class used by the reference screenshot)
- **Viewport (mobile):** 390 x 844
- **Route:** `/assistant?plant=Monty&binomial=Monstera%20deliciosa&scientific=Monstera%20deliciosa`
- **State:** Empty thread and a thread with one user + one assistant message
- **Source:** Live dev server (Next.js) with a mocked `/api/assistant/chat` response for the with-message screenshot (the live API was unavailable during the screenshot run)

## Screenshots

- `desktop-empty.png` - Plant-context session before the user sends a message.
- `desktop-with-message.png` - Plant-context session after one user message and one assistant response.
- `desktop-no-context.png` - No-plant-context session showing the chat usable without an empty sidebar.
- `mobile-with-message.png` - Mobile viewport of the same conversation.

## Reference Comparison

The implementation matches `frontend/REFERENCES/asistente_ai/screen.png` for:

- Two-column desktop workspace (320px sidebar + main chat area)
- Sidebar structure: back action, square image placeholder, "Apodo" + "Nombre cientifico" labels, "Ubicacion" + "Notas del usuario" placeholders, "Ver ficha completa" action
- Main chat: assistant bubbles use the primary green, user bubbles use the secondary brown, both with rounded corners and a smaller radius on the attachment side
- Avatar circle on each message (spark icon for assistant, person for the user)
- Labels above each bubble ("Asistente AI" / "Tu")
- Anchored composer at the bottom of the chat area with attach icon, textarea, "Enviar" send button, and the AI disclaimer
- Tone, surfaces, borders, radii, and typography follow the archived Fotosintesis design tokens

## Intentional Visual Deviations

1. **Product copy:** "PlantCare" is replaced with "Fotosintesis" in user-facing copy (header title, source links, buttons, and the conversation placeholder).
2. **Top bar:** The reference's sticky top bar with "PlantCare" + notifications + account is replaced by the existing private shell top bar (Fotosintesis brand + private navigation + logout). The new top bar is owned by the AppShell so it stays consistent with the other private surfaces.
3. **Page header:** The reference's centered top brand is replaced by an in-canvas task-focused header (eyebrow "Asistente AI", title "Fotosintesis", description) to keep the existing AppShell canvas width and avoid a duplicate top bar.
4. **Sidebar image/location/notes:** The reference shows a plant photograph and a "Sala de estar" location. The assistant route does not currently fetch garden detail data, so the image uses a neutral placeholder and the location/notes fields show neutral placeholder text. No botanical or user-specific facts are invented.
5. **Composer anchoring:** On desktop the composer is anchored inside the chat area (not viewport-fixed) so the AppShell footer can render normally. On mobile the composer is part of the normal flow with the bottom safe spacing provided by the AppShell canvas, which prevents overlap with the bottom navigation. The visual effect is similar to the reference but avoids creating overlapping fixed controls.
6. **Mobile single column:** The sidebar is hidden below 960px to keep the chat usable inside the private shell with no horizontal overflow and no composer conflict with the bottom navigation. The reference's sidebar structure is preserved for desktop only.
7. **Width:** The assistant is constrained by the AppShell canvas (max 58rem). The reference uses a full viewport width, so the live implementation is narrower while keeping the same internal proportions, spacing, and hierarchy.

## Component Test Coverage

`pnpm test -- AssistantChat` covers the preserved assistant behavior:

- Reminder suggestion card structure, action label, plant + date + recurrence, justification
- Reminder suggestion acceptance payload mapping and disabled duplicate acceptance
- Taxonomy query parameter mapping (plant, binomial, scientific) to the chat request payload
- Plant-only assistant request compatibility (no binomial/scientific)
- Raw-text assistant message rendering with newline preservation
- Raw-text rendering of markdown-labeled and unsupported future content formats
- Retryable error rendering without appending an assistant bubble
- Source link rendering with title/domain/URL fallback
- Conversation id continuation across successful responses

All 10 component tests pass, and the broader vitest suite (104 tests across 25 files) still passes.

## End-to-End Notes

`pnpm test:e2e` was attempted for the assistant journey. The pre-existing `assistant RAG and light fallback flows render` test was already failing on the baseline commit due to a login/auth issue in the shared `beforeEach` at `frontend/e2e/mvp-journeys.spec.ts:13`. The registration succeeds (URL becomes `/login?registered=1`) but the subsequent `Ingresar` click does not redirect to `/home`, so every test that depends on the shared auth setup is blocked at line 13 before it can reach `/assistant`. The failure is unrelated to the assistant redesign: it reproduces on the unmodified baseline with the assistant code reverted. Fixing the e2e auth setup is out of scope for this change.

The e2e route, placeholder (`Ej: Como ajusto el riego de mi Monstera?`), and `Enviar` button contract that the existing e2e tests rely on are preserved by the implementation, so the existing assistant journey test should pass once the shared auth setup is fixed.

A new e2e test, `assistant keeps plant context sidebar from query parameters`, was added to verify that the redesigned route accepts the existing `plant`, `binomial`, and `scientific` query parameters and renders the new sidebar with the expected labels (complementary landmark, "Apodo" / "Nombre cientifico" values, "Volver al detalle" and "Ver ficha completa" actions) and the composer. The test uses the shared `beforeEach` so it is also currently blocked by the pre-existing auth failure. The test is structurally correct and ready to run once the e2e auth setup is restored.

**E2e status:** incomplete. The new test exists and is structurally correct but cannot be exercised end-to-end until the shared e2e auth setup at `frontend/e2e/mvp-journeys.spec.ts:13` is fixed. Component tests (`pnpm test -- AssistantChat`) and live visual verification (screenshots above) cover the same behavior in the meantime.
