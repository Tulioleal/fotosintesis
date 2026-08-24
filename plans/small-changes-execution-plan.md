# Small Changes — Execution Plan

Generated 2026-08-24. Companion to proposals 16–19 in `proposals/`. This covers only the
quick fixes that need **no new spec**. Nothing here is committed until each item is verified.

Assumptions agreed so far:

- E2 gets the honest-copy fix now (no new retry endpoint yet).
- "Sidebar always visible" = page scrolling under nav; fixed by internal chat scroll.
- Fallback stays model-generated (no reintroduced hardcoded sentence).
- Timezone quick-fixes land BEFORE proposal 18, which supersedes parts of them.

Sequencing rationale: Phase 0 unblocks live verification of everything else;
Phase 1 is the most user-visible; backend phases follow; hygiene last.

Commit style: repo convention (`fix:` / `feature:` / `chore:`), one commit per numbered
item or tight group. NEVER batch across phases.

---

## Phase 0 — Ops unblock

| # | Change | Files | Verify |
|---|--------|-------|--------|
| 0.1 | Restart worker: `docker compose up -d worker`; add `restart: unless-stopped` + healthcheck to the `worker` service | `docker-compose.yml` | Stuck `processing` jobs reconcile after lease expiry (~300 s); confirming a candidate reaches `complete/partial`; `docker ps` shows worker Up |

## Phase 1 — Chat UX bundle (frontend-only)

| # | Change | Files |
|---|--------|-------|
| 1.1 | Bounded app viewport so `.chatArea` actually scrolls internally: shell becomes `height:100dvh` flex column; canvas gets `min-height:0; overflow:hidden` on assistant route (use existing `canvasFullBleed` variant) | `frontend/src/components/layout/AppShell.module.scss`, `frontend/src/app/(private)/layout.tsx`, `AssistantChat.module.scss` |
| 1.2 | Pin composer on mobile (≤719px): restore sticky positioning + bottom-nav/safe-area clearance (`env(safe-area-inset-bottom)` + nav height padding) | `AssistantChat.module.scss:512-532` |
| 1.3 | Auto-scroll to newest message / pending indicator (ref + effect; respect `prefers-reduced-motion`) | `AssistantChat.tsx` |
| 1.4 | Rotating pending-stage copy while awaiting response ("Clasificando tu consulta…" → "Buscando en fuentes confiables…" → "Contrastando información…" → "Redactando respuesta…"), ~3–4 s interval, inside existing `aria-live` region. NOTE: superseded later by proposal 19 streaming — keep isolated in one helper so removal is trivial | `AssistantChat.tsx:363-367` |

Tests to update/add in `AssistantChat.test.tsx`: pending copy rotation, composer pinned
class present at mobile breakpoint, auto-scroll effect invocation.

Verify: `pnpm --filter frontend test lint typecheck build`. Manual pass at 375px and
1280px widths per frontend-visual-system spec (visual verification state required).

## Phase 2 — Reminders quick fixes

| # | Change | Files |
|---|--------|-------|
| 2.1 | Add missing BFF proxy `/api/reminders/suggestions/metrics/route.ts` (mirror `suggestions/route.ts`: resolve auth headers, forward POST verbatim, same error mapping) | new `frontend/src/app/api/reminders/suggestions/metrics/route.ts` |
| 2.2a | Backend tz: `_extract_due_at` builds due datetime in the USER's timezone via `scheduling/timezone.py` helpers instead of stamping UTC | `backend/app/assistant/graph/graph_shared.py:124-129`, graph state plumbing for user tz |
| 2.2b | Frontend tz: acceptance derives date/time in `suggestion.timezone` using `Intl.DateTimeFormat` instead of slicing ISO instant (`due_at.slice(0,10)`/`.slice(11,16)`) | `frontend/src/components/assistant/AssistantChat.tsx:135-136` |

Update tests: `AssistantChat.test.tsx:78-124` (bakes in slicing), reminder suites.
Known overlap: proposal 18 supersedes both 2.2a/b at contract level — keep changes minimal
and well-named for easy fold-in.

Verify: `pytest backend/tests/test_assistant_agent_part7.py backend/tests/test_reminders.py`;
frontend vitest; manual: create reminder from page flow with a non-UTC profile tz and
confirm stored instant matches local wall clock.

## Phase 3 — Enrichment fixes (backend + copy)

| # | Change | Files |
|---|--------|-------|
| 3.1 | E1: if ≥1 acquisition group hit a transient provider error AND overall coverage ends insufficient → raise retryable provider error instead of permanent `insufficient_evidence`. Track per-group failures (`completed_groups` already tracked but discarded at `acquisition.py:93`) | `backend/app/enrichment/acquisition.py:93-102` + unit tests |
| 3.2 | E2: replace false-retry copy "podés revisar el perfil para intentar ampliar la evidencia nuevamente" with honest terminal copy (e.g., "La ampliación de evidencia no pudo completarse. El perfil sigue disponible con la evidencia actual.") | `frontend/src/lib/enrichment-activity.ts:317`; check `PlantProfileView.tsx:43-50` limitation map for consistency |

Verify: `pytest backend/tests/integration/ -k enrichment`; `pnpm e2e:enrichment` with
Phase 0's worker running; confirm failed evidence-phase announcement shows new copy.

## Phase 4 — Hygiene

| # | Change | Files |
|---|--------|-------|
| 4.1 | Fix eval doc command (`python -m app.evaluation.runner` → `python scripts/run_evaluation.py --mode recorded`); add root `"eval"` script | `DOCS/local-docker-compose.md:92`, root `package.json` |
| 4.2 | Dead code removal: `_is_safety_sensitive_question()` stubs (`graph/safety.py:9-10`, `web_evidence.py:446-447` + dead `_safety_constrained_covered_aspects`), vestigial `_conservative_safety_answer` prose gate (`answers.py:100-107`), unused answerability shims (one referenced by `tests/test_assistant_agent_part9.py:255` — update or drop test), empty `PLANT_CONTEXT_HINTS`, `aspect_metadata.py` re-export (verify no importers first) | see left |
| 4.3 | Render suggestion evidence/confidence/limitations on `SuggestionOutcomeCard` (data already delivered by API; add muted lines + confidence % chip) | `RemindersManager.tsx:1094-1130` + test |
| 4.4 | Spec-text reconciliation: delete stale "MUST NOT schedule profile-refresh" requirement/scenarios (Proposal 11 paragraph) — code follows newer background-enrichment-tracker spec | `openspec/specs/confirmed-plant-enrichment/spec.md:390-399` |

Verify: full `pytest backend/tests`; grep confirms removed symbols have no remaining
importers; `pnpm --filter frontend test`.

---

## Definition of done (per item)

1. Code change + tests updated/added.
2. Lint + typecheck green for touched workspace(s).
3. Targeted tests green; phase-level verification commands run.
4. One commit with conventional prefix referencing this plan item (e.g., `fix: retry enrichment acquisition when provider outage is partial`).

## Explicitly out of scope here

Everything in proposals 16–19 (quality gate, plant image display, chat reminder
contract alignment, SSE progress streaming). Those follow the OpenSpec flow after review.
