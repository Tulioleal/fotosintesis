## Why

The current frontend uses 16 hand-rolled SVG icons in `frontend/src/components/ui/icons.tsx` wrapped by a custom `Icon` React component. This bloats the design system: every new icon needs a new SVG path constant plus a wrapping function, the tone/size/variant API is bespoke, and there is no shared, recognizable style with the rest of the design ecosystem. The hand-rolled icons also lack accessibility patterns, drop-in tree-shakeable imports, and an established visual family for the solid botanical feel the design mandates.

## What Changes

- Adopt `@phosphor-icons/react` v2 as the single shared icon source for the frontend.
- Drop the custom `Icon` wrapper component and the `icons.tsx` re-export shim; call sites import Phosphor components directly.
- Consolidate the six existing tone colors (`primary`, `secondary`, `muted`, `onPrimary`, `onSurfaceVariant`, `error`) into shared SCSS tone utility classes under `frontend/src/components/ui/Icons.module.scss`.
- Provide global defaults (color: `currentColor`, size: `20`, weight: `fill`) via `IconContext.Provider` in `frontend/src/app/providers.tsx`.
- Collapse the previous `PotIcon` and `SproutIcon` to Phosphor's `PlantIcon` (accepted visual change; the home garden tile, identify tile, hero art, and identify empty state now share the same potted plant icon).
- Map `DropletIcon → DropIcon`, `PersonIcon → UserIcon`, `SparkIcon → BrainIcon`, `ArrowUpwardIcon → ArrowUpIcon`, `AttachFileIcon → PaperclipIcon`, `LocationOnIcon → MapPinIcon`, `ArrowBackIcon → ArrowLeftIcon`, `MoreVertIcon → DotsThreeVerticalIcon`. Names that already match Phosphor (`LeafIcon`, `SunIcon`, `CameraIcon`, `BellIcon`, `SparkleIcon`, `ImageIcon`) keep their names.
- Per-site `weight="regular"` on stroke-style icons (`ArrowLeftIcon`, `ArrowUpIcon`, `PaperclipIcon`) preserves the previously-outlined look.
- Delete the obsolete `frontend/src/components/ui/Icon.tsx`, `frontend/src/components/ui/Icon.module.scss`, and `frontend/src/components/ui/icons.tsx` files.

## Capabilities

### Modified Capabilities

- `frontend-visual-system`: The icon strategy requirement switches from the custom botanical icon set to Phosphor Icons with `weight="fill"`, with the tone color applied through shared SCSS utility classes referenced as `className` on the icon component.

## Impact

- Affected frontend code: `frontend/src/app/page.tsx`, `frontend/src/app/(auth)/welcome/page.tsx`, `frontend/src/components/ui/PlaceholderPage.tsx`, `frontend/src/components/ui/index.ts`, `frontend/src/components/ui/Icons.module.scss` (new), `frontend/src/components/ui/Icon.test.tsx` (rewritten), `frontend/src/app/providers.tsx`, `frontend/src/components/home/HomeDashboard.tsx`, `frontend/src/components/reminders/RemindersManager.tsx`, `frontend/src/components/assistant/AssistantChat.tsx`, `frontend/src/components/assistant/AssistantChat.test.tsx`, `frontend/src/components/identify/IdentifyFlow.tsx`, `frontend/src/components/light-meter/LightMeter.tsx`.
- Visual change: the home dashboard "garden" tile, the home dashboard "identify" tile, the home hero art, and the identify empty state now display the same `PlantIcon`. The sparkle icon moves from outlined (variant stroke) to filled (`weight="fill"`).
- New package: `@phosphor-icons/react@^2.1.10` added to `frontend/package.json`.
- Server-rendered pages (`frontend/src/app/page.tsx`, `frontend/src/app/(auth)/welcome/page.tsx`, `frontend/src/components/ui/PlaceholderPage.tsx`) import icons from the `@phosphor-icons/react/ssr` entry point. The default entry point's `IconBase` imports `IconContext` which calls `React.createContext` at module load, and that breaks Next.js 15 server rendering of pages that are not marked `"use client"`. The SSR entry exposes the same icon components without the `IconContext` dependency, so server-rendered trees work. However, the SSR entry's `SSRBase` defaults `weight` to `"regular"` instead of `"fill"`, and the `IconContext.Provider` does not affect the `/ssr` entry's components — so every server-rendered icon MUST be passed `weight="fill"` explicitly to honor the solid botanical look. The seven affected call sites are: `frontend/src/app/page.tsx:18, 26, 34, 83, 181`; `frontend/src/app/(auth)/welcome/page.tsx:12`; `frontend/src/components/ui/PlaceholderPage.tsx:17`.
- Test changes: `Icon.test.tsx` rewrites to assert Phosphor accessibility behavior (decorative `aria-hidden`, informative `<title>` from `alt`); `AssistantChat.test.tsx` no longer asserts the `variant-stroke` class.
- Public-API impact: the `Icon`, `IconProps`, `IconSize`, `IconTone` types and the named icon exports (`BellIcon`, `CameraIcon`, `DropletIcon`, `LeafIcon`, `MoreVertIcon`, `PotIcon`, `SparkleIcon`, `SproutIcon`, `SunIcon`) are removed from `frontend/src/components/ui`.
