## 1. Install the package and set up global defaults

- [x] 1.1 Add `@phosphor-icons/react` v2 to `frontend/package.json` via `pnpm --filter frontend add @phosphor-icons/react`.
- [x] 1.2 Wrap the children of `frontend/src/app/providers.tsx` with `IconContext.Provider` providing `{ color: "currentColor", size: 20, weight: "fill" }`.

## 2. Tone utility classes and shared icon module

- [x] 2.1 Create `frontend/src/components/ui/Icons.module.scss` with `.tonePrimary`, `.toneSecondary`, `.toneMuted`, `.toneOnSurfaceVariant`, `.toneOnPrimary`, `.toneError` classes, each setting `color` to the matching `$color-*` token from `frontend/src/styles/_tokens.scss`.
- [x] 2.2 Update `frontend/src/components/ui/index.ts` to remove the `Icon`, `IconProps`, `IconSize`, `IconTone` re-exports and the named-icon re-exports (`BellIcon`, `CameraIcon`, `DropletIcon`, `LeafIcon`, `MoreVertIcon`, `PotIcon`, `SparkleIcon`, `SproutIcon`, `SunIcon`).

## 3. Migrate call sites to Phosphor

- [x] 3.1 `frontend/src/components/light-meter/LightMeter.tsx` — switch `BellIcon`, `CameraIcon`, `SunIcon` to Phosphor with `iconStyles.tone*` className and per-site `size`.
- [x] 3.2 `frontend/src/components/identify/IdentifyFlow.tsx` — switch `CameraIcon`, `LeafIcon`, `SparkleIcon`, and rename `SproutIcon → PlantIcon` with `iconStyles.tone*` className and per-site `size`.
- [x] 3.3 `frontend/src/components/home/HomeDashboard.tsx` — switch all seven icons, collapse `PotIcon` and `SproutIcon` to `PlantIcon`, retype the `accessIcons` map to `Record<string, React.ComponentType<IconProps>>`.
- [x] 3.4 `frontend/src/app/page.tsx` — switch `CameraIcon`, `LeafIcon`, `SunIcon`, rename `DropletIcon → DropIcon` and `PotIcon → PlantIcon`; import from `@phosphor-icons/react/ssr` because the page is server-rendered, and pass `weight="fill"` to every icon because the `/ssr` entry's default weight is `"regular"`.
- [x] 3.5 `frontend/src/app/(auth)/welcome/page.tsx` — switch the `LeafIcon` to Phosphor via `@phosphor-icons/react/ssr`, and pass `weight="fill"`.
- [x] 3.6 `frontend/src/components/ui/PlaceholderPage.tsx` — switch the `LeafIcon` to Phosphor via `@phosphor-icons/react/ssr`, and pass `weight="fill"`.
- [x] 3.7 `frontend/src/components/reminders/RemindersManager.tsx` — switch `BellIcon`, `SparkleIcon`, rename `MoreVertIcon → DotsThreeVerticalIcon` and `PotIcon → PlantIcon`; drop the `TASK_ICON_SIZE` constant.
- [x] 3.8 `frontend/src/components/assistant/AssistantChat.tsx` — switch all eight icons: rename `ArrowBackIcon → ArrowLeftIcon` (with `weight="regular"`), `ArrowUpwardIcon → ArrowUpIcon` (with `weight="regular"`), `AttachFileIcon → PaperclipIcon` (with `weight="regular"`), `LocationOnIcon → MapPinIcon`, `PersonIcon → UserIcon`, `SparkIcon → BrainIcon`; keep `ImageIcon` and `LeafIcon`.

## 4. Tests and obsolete files

- [x] 4.1 Rewrite `frontend/src/components/ui/Icon.test.tsx` to assert Phosphor accessibility (decorative `aria-hidden`, informative `<title>` from `alt` prop) and stroke-style `weight="regular"` rendering.
- [x] 4.2 Update `frontend/src/components/assistant/AssistantChat.test.tsx` to drop the `variant-stroke` class assertions and assert svg presence in the composer, back, and attach buttons.
- [x] 4.3 Delete `frontend/src/components/ui/icons.tsx`, `frontend/src/components/ui/Icon.tsx`, and `frontend/src/components/ui/Icon.module.scss`.

## 5. Spec and design reference

- [x] 5.1 Update `frontend/REFERENCES/fotosintesis/DESIGN.md` to mention Phosphor Icons with `weight="fill"`.
- [x] 5.2 Update the `Icon strategy` requirement in `openspec/specs/frontend-visual-system/spec.md` to reference Phosphor, the global `IconContext.Provider` defaults, shared SCSS tone utility classes, and Phosphor's `alt` prop for accessible labels.

## 6. Verification

- [x] 6.1 `pnpm --filter frontend typecheck` exits 0.
- [x] 6.2 `pnpm --filter frontend lint` exits 0.
- [x] 6.3 `pnpm --filter frontend test` exits 0.
- [x] 6.4 `pnpm --filter frontend build` exits 0.
