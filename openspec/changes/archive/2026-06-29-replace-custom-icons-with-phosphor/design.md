## Context

`frontend/src/components/ui/icons.tsx` ships 16 hand-rolled SVG icons wrapped by a bespoke `Icon` React component in `frontend/src/components/ui/Icon.tsx:1-88` with tone, size, and variant APIs that only the design system understands. Every new icon needs a new SVG path constant plus a wrapping function, the tone palette is split between the SCSS module and a TS string-union, and the icon set is not aligned with the wider material/botanical iconography direction captured in `frontend/REFERENCES/fotosintesis/DESIGN.md:154`.

The design mandate is a "Clean Botanical" aesthetic with a solid/fill weight. The existing icons mostly render as solid paths but a handful (`SparkleIcon`, `ArrowUpwardIcon`, `AttachFileIcon`, `ArrowBackIcon`) use a stroke variant to stay visible, which means tone and visual weight are spread across the wrapper component instead of the icon itself.

`@phosphor-icons/react` v2 is already a widely-used icon family that ships every icon we need, supports per-icon tree-shakeable imports, exposes a `weight="fill"` style for the solid botanical look, and provides an `IconContext.Provider` for global defaults. Adopting it lets the frontend drop the wrapper component, expose a single tone system through shared SCSS utility classes, and align with a recognized visual family without an in-house SVG maintenance burden.

## Goals / Non-Goals

**Goals:**

- Replace the 16 hand-rolled icons and the `Icon` wrapper component with `@phosphor-icons/react` v2 imports.
- Preserve the solid/fill "botanical" look across the public landing page, the auth welcome page, the home dashboard, the identify flow, the reminders manager, the assistant chat, and the light meter.
- Preserve the six existing tone colors (primary, secondary, muted, onPrimary, onSurfaceVariant, error) by mapping them to shared SCSS utility classes that are referenced as `className` on each icon component.
- Provide global defaults (`color: "currentColor"`, `size: 20`, `weight: "fill"`) through `IconContext.Provider` in `frontend/src/app/providers.tsx` so client-rendered trees get the fill style by default.
- Collapse the previous `PotIcon` and `SproutIcon` to Phosphor's `PlantIcon` (visual change accepted in the original plan).
- Keep the per-site stroke look for the back, submit, and attach buttons in the assistant composer by passing `weight="regular"` at the call site rather than reintroducing a separate icon set.
- Update `frontend/REFERENCES/fotosintesis/DESIGN.md` and the `Icon strategy` requirement in `openspec/specs/frontend-visual-system/spec.md` to match the new shared icon source.

**Non-Goals:**

- No changes to backend, RAG, classifier, answerability, garden, or profile flows.
- No redesigns of any feature screen beyond the icon substitution and its tone/size adjustments.
- No re-architecting of the shared UI primitives (Button, Card, Field, Chip, Notice, PageHeader, ImageCard, PlaceholderPage) — they keep their existing API and styling.
- No new icon dependency beyond `@phosphor-icons/react` itself.
- No introduction of a bespoke icon abstraction layer; call sites import Phosphor components directly.
- No changes to the OpenSpec workflow, change directory layout, or verification commands.
- No introduction of deterministic keyword matching, language detection, or semantic plant-care heuristics.

## Decisions

### Decision 1: Use `@phosphor-icons/react` v2 as the single shared icon source

The frontend shall depend on `@phosphor-icons/react@^2.1.10` (latest 2.x at the time of the change) and import each icon directly from the package. The `frontend/src/components/ui/icons.tsx`, `frontend/src/components/ui/Icon.tsx`, and `frontend/src/components/ui/Icon.module.scss` files are deleted because their responsibilities move into Phosphor and the shared `frontend/src/components/ui/Icons.module.scss` tone utility classes.

Alternative considered: keep the wrapper component and only swap the SVG bodies. Rejected because the wrapper API (`size`/`tone`/`variant`/`decorative`) duplicates concerns that Phosphor already handles (per-icon props, `IconContext.Provider`, `weight`). The wrapper adds maintenance surface and prevents tree-shaking the way Phosphor expects.

Alternative considered: introduce a third `frontend/src/components/ui/Icon.tsx` that re-exports Phosphor icons with our tone/size defaults pre-applied. Rejected because it reintroduces a wrapper the plan explicitly drops, and it would force every new icon through a fork instead of pulling from `@phosphor-icons/react` directly.

### Decision 2: Consolidate tone color through shared SCSS utility classes

The six tone colors that the old `Icon` component accepted map to six SCSS classes in `frontend/src/components/ui/Icons.module.scss` (`.tonePrimary`, `.toneSecondary`, `.toneMuted`, `.toneOnSurfaceVariant`, `.toneOnPrimary`, `.toneError`). Each class sets `color` to the matching `$color-*` token from `frontend/src/styles/_tokens.scss`, and call sites reference the class via `className={iconStyles.toneXxx}`. Phosphor icons inherit the surrounding `color` because their default `color` is `currentColor`, so the tone cascades naturally.

Alternative considered: keep a TS `tone` prop on each call site and pass it as `color={...}`. Rejected because it reintroduces a tone system parallel to the SCSS tokens, and SCSS classes already participate in the design-system cascade. Per-site `color` strings also break the source-of-truth for color values.

### Decision 3: Server-rendered pages import from `@phosphor-icons/react/ssr`

The Next.js 15 server renderer can fail when a server component imports the default `@phosphor-icons/react` entry, because the default entry's `IconBase` chains to `IconContext`, and `IconContext` calls `React.createContext` at module load. The `/ssr` entry exposes the same icon components without the `IconContext` dependency, so server-rendered pages (`/`, `/welcome`, `/search` via `PlaceholderPage`) import from `@phosphor-icons/react/ssr` while client components (IdentifyFlow, RemindersManager, AssistantChat, LightMeter, HomeDashboard) keep importing from the main entry so they remain under the global `IconContext.Provider` defaults.

Alternative considered: add `"use client"` to the public landing page, welcome page, and `PlaceholderPage`. Rejected because the public landing and welcome pages intentionally remain server components for static rendering and smallest client bundle, and `PlaceholderPage` is reused by multiple server-rendered routes.

### Decision 4: SSR-imported icons must pass `weight="fill"` explicitly

The `/ssr` entry's `SSRBase` component defaults `weight` to `"regular"` instead of `"fill"`, and `IconContext.Provider` does not affect the `/ssr` entry's components. To honor the solid botanical look on every server-rendered surface, every icon imported from `@phosphor-icons/react/ssr` must pass `weight="fill"` at the call site. The seven affected call sites are `frontend/src/app/page.tsx:18, 26, 34, 83, 181`, `frontend/src/app/(auth)/welcome/page.tsx:12`, and `frontend/src/components/ui/PlaceholderPage.tsx:17`.

Alternative considered: build a thin server-safe icon helper that re-exports each Phosphor icon with `weight="fill"` pre-applied. Rejected as unnecessary indirection — the seven call sites are explicit and the `weight="fill"` prop makes the contract visible at every usage. If the repetition grows, a future change can introduce the helper.

### Decision 5: Drop the variant concept and use `weight` per site

The old `Icon` component supported `variant="fill"` and `variant="stroke"`. Phosphor encodes the same idea through the `weight` prop (`"thin" | "light" | "regular" | "bold" | "fill" | "duotone"`). The default `weight="fill"` (set globally for the client tree via `IconContext.Provider`) preserves the solid look. The three stroke-style icons used by the assistant composer — `ArrowLeftIcon`, `ArrowUpIcon`, and `PaperclipIcon` — pass `weight="regular"` at their call sites to keep the previously-outlined look without reintroducing a separate icon set.

Alternative considered: keep the `variant` prop and translate it to `weight` inside a small adapter. Rejected because the call-site `weight="regular"` is a one-token change and the old `variant` API does not need to survive the migration.

### Decision 6: Drop the `Icon` / `IconProps` / `IconSize` / `IconTone` exports from the shared UI barrel

`frontend/src/components/ui/index.ts` previously re-exported the wrapper component, its props, its size/tone unions, and the named icon components. None of those symbols are part of the new system, so they are removed. The new barrel exposes only `Button`, `Card`, `Chip`, `Field`, `ImageCard`, `Notice`, `PageHeader`, and `PlaceholderPage` (each with their existing types). Call sites import icons directly from `@phosphor-icons/react` or `@phosphor-icons/react/ssr`.

Alternative considered: keep the barrel re-exports pointing at the Phosphor components so existing imports continue to work. Rejected because the public API surface should not pretend the wrapper still exists, and the existing call sites are already being updated.

## Risks / Trade-offs

- **Risk: Server-rendered icons default to `weight="regular"` and silently render as outlines.** → Mitigation: every SSR-imported icon call site passes `weight="fill"` explicitly; visual smoke test confirms filled paths on `/`, `/welcome`, and `/search` (via `PlaceholderPage`).
- **Risk: Bundle grows by 15–22 KB gzipped.** → Measurement on the production build shows the Phosphor vendor chunk is ~20.5 KB gzipped, in the expected range. Per-icon imports are tree-shakeable; only the 15 icons in actual use are bundled on each route.
- **Risk: Pot + Sprout collapse to the same `PlantIcon`.** → Accepted per the original plan. The home dashboard "garden" tile, "identify" tile, hero art, and identify empty state now share the same potted plant. If the visual reads as flat, a follow-up can change SproutIcon's import to `TreeEvergreenIcon` or `TreeIcon` in `HomeDashboard.tsx:18-24` and `IdentifyFlow.tsx`.
- **Risk: SparkleIcon moved from outlined (`variant="stroke"`) to filled (`weight="fill"`) by default.** → Accepted per the original plan. If outlined sparkle is preferred, the call sites in `IdentifyFlow.tsx` and `RemindersManager.tsx` can add `weight="regular"`.
- **Risk: `IconContext.Provider` does not affect the `/ssr` entry.** → Mitigation: server-rendered call sites pass `weight="fill"` explicitly (see Decision 4). Future maintainers who add new SSR-imported icons must do the same; the OpenSpec `Icon strategy` requirement spells this out.
- **Risk: `Icon`, `IconProps`, `IconSize`, `IconTone`, and the named icon re-exports are removed from the shared UI barrel.** → This is a public API change for the `@/components/ui` module. Mitigation: the only internal consumers were the seven migrated call sites and the deleted test; no other modules import these symbols.
- **Risk: `TASK_ICON_SIZE` constant removal shifts the bell-icon size in the reminders list.** → The `width="1.1rem"` / `height="1.1rem"` override is replaced by `size="1.1rem"`, which produces the same rendered size. If the visual size drifts, adjust the value in `RemindersManager.tsx:80-85`.
- **Risk: Per-site `weight="regular"` looks slightly different from the old `variant="stroke"`.** → Phosphor's `weight="regular"` is a thin outline, visually close to the old `variant="stroke"`. Accepted per the original plan's risk register.

## Migration Plan

1. Add `@phosphor-icons/react@^2.1.10` to `frontend/package.json` via `pnpm --filter frontend add @phosphor-icons/react`.
2. Wrap the children of `frontend/src/app/providers.tsx` with `IconContext.Provider` providing `{ color: "currentColor", size: 20, weight: "fill" }`.
3. Create `frontend/src/components/ui/Icons.module.scss` with the six `.tone-*` classes; confirm the `$color-*` token names against `frontend/src/styles/_tokens.scss`.
4. Update `frontend/src/components/ui/index.ts` to remove the `Icon`, `IconProps`, `IconSize`, `IconTone` re-exports and the named-icon re-exports.
5. Migrate call sites in this order (lowest risk first):
   1. `frontend/src/components/light-meter/LightMeter.tsx` — same-name icons only.
   2. `frontend/src/components/identify/IdentifyFlow.tsx` — `SproutIcon` → `PlantIcon`.
   3. `frontend/src/components/home/HomeDashboard.tsx` — `PotIcon` + `SproutIcon` → `PlantIcon`; retype the `accessIcons` map.
   4. `frontend/src/app/page.tsx` — server component, import from `@phosphor-icons/react/ssr`, pass `weight="fill"`.
   5. `frontend/src/app/(auth)/welcome/page.tsx` — server component, import from `@phosphor-icons/react/ssr`, pass `weight="fill"`.
   6. `frontend/src/components/ui/PlaceholderPage.tsx` — server component, import from `@phosphor-icons/react/ssr`, pass `weight="fill"`.
   7. `frontend/src/components/reminders/RemindersManager.tsx` — `MoreVertIcon` → `DotsThreeVerticalIcon`, `PotIcon` → `PlantIcon`, drop `TASK_ICON_SIZE`.
   8. `frontend/src/components/assistant/AssistantChat.tsx` — `ArrowBackIcon` → `ArrowLeftIcon`, `ArrowUpwardIcon` → `ArrowUpIcon`, `AttachFileIcon` → `PaperclipIcon`, `LocationOnIcon` → `MapPinIcon`, `PersonIcon` → `UserIcon`, `SparkIcon` → `BrainIcon`; pass `weight="regular"` on the three stroke-style icons.
6. Rewrite `frontend/src/components/ui/Icon.test.tsx` to assert Phosphor accessibility behavior (decorative `aria-hidden`, informative `<title>` from `alt`).
7. Update `frontend/src/components/assistant/AssistantChat.test.tsx` to drop the `variant-stroke` class assertions.
8. Delete `frontend/src/components/ui/icons.tsx`, `frontend/src/components/ui/Icon.tsx`, and `frontend/src/components/ui/Icon.module.scss`.
9. Update `frontend/REFERENCES/fotosintesis/DESIGN.md` to mention Phosphor Icons with `weight="fill"`.
10. Update the `Icon strategy` requirement in `openspec/specs/frontend-visual-system/spec.md`.
11. Run `pnpm --filter frontend typecheck`, `pnpm --filter frontend lint`, `pnpm --filter frontend test`, and `pnpm --filter frontend build` and confirm all four exit 0.
12. Visually smoke-test `/`, `/welcome`, and a private route that renders through `PlaceholderPage` to confirm the icons render as filled paths.

Rollback is source-only: revert the changes to `frontend/package.json`, the new `frontend/src/components/ui/Icons.module.scss`, `frontend/src/app/providers.tsx`, `frontend/src/components/ui/index.ts`, the seven call sites, the two test files, `frontend/REFERENCES/fotosintesis/DESIGN.md`, and `openspec/specs/frontend-visual-system/spec.md`, and restore `frontend/src/components/ui/icons.tsx`, `Icon.tsx`, and `Icon.module.scss`. No backend change, data migration, or persisted state migration is involved.

## Open Questions

- Whether the home dashboard "garden" and "identify" tiles need a future visual differentiator once they share the same `PlantIcon` (e.g. swap the "identify" tile's import to `TreeEvergreenIcon` or `CameraIcon`).
- Whether the `SparkleIcon` should be re-introduced with `weight="regular"` at the assistant suggestion and identify results call sites to recover the previously-outlined sparkle look without affecting the migration.
