## Why

The Fotosíntesis visual foundation and private shell/home redesign are complete, but unauthenticated users still enter through public and authentication screens that do not match the new product identity. This change aligns the public landing, welcome, login, registration, and recovery entry flow with the archived Fotosíntesis design system before deeper feature screens are redesigned.

## What Changes

- Redesign the public landing/welcome experience using `frontend/REFERENCES/bienvenida_con_funcionalidades/screen.png` and `frontend/REFERENCES/bienvenida_con_funcionalidades/code.html` as visual references.
- Redesign the login page using `frontend/REFERENCES/iniciar_sesi_n/screen.png` and `frontend/REFERENCES/iniciar_sesi_n/code.html` as visual references.
- Redesign the register page using `frontend/REFERENCES/crear_cuenta/screen.png` and `frontend/REFERENCES/crear_cuenta/code.html` as visual references.
- Apply the same transactional authentication layout style to forgot-password/recovery if the page remains in the implemented auth flow.
- Use the archived Fotosíntesis visual system as the required baseline for colors, typography, spacing, radii, surfaces, outlines, elevation, and responsive layout.
- Keep visible product naming consistently as `Fotosíntesis`, adapting placeholder reference copy such as `PlantCare` to real product copy.
- Preserve existing authentication behavior, validation behavior, redirects, callback URL handling, registration success flow, recovery contract, session handling, and test-facing accessible form labels/button names unless this change explicitly updates visible copy.
- Avoid changing private feature pages or redesigning authenticated feature surfaces in this change.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `frontend-visual-system`: Extend the archived Fotosíntesis visual-system contract to public and authentication entry surfaces.
- `authentication-home`: Add public/auth presentation requirements while preserving the existing authentication, recovery, redirect, and session behavior requirements.

## Impact

- Affected frontend routes and styles: `src/app/page.tsx`, `src/app/page.module.scss`, `src/app/(auth)/welcome/page.tsx`, `src/app/(auth)/login/page.tsx`, `src/app/(auth)/register/page.tsx`, and `src/app/(auth)/forgot-password/page.tsx`.
- Affected auth components: `src/components/auth/AuthShell.tsx`, `src/components/auth/AuthShell.module.scss`, `src/components/auth/LoginForm.tsx`, `src/components/auth/RegisterForm.tsx`, and `src/components/auth/RecoveryForm.tsx`.
- Affected tests: relevant auth/home unit tests and Playwright/e2e coverage for unauthenticated entry, registration, login, recovery, redirects, and accessible form interactions.
- No backend API, authentication provider, database, session, or private feature behavior changes are intended.
