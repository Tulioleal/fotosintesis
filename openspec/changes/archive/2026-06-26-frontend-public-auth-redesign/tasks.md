## 1. Public Entry Redesign

- [x] 1.1 Replace the public root foundation proof content in `frontend/src/app/page.tsx` with a Fotosíntesis landing experience based on `frontend/REFERENCES/bienvenida_con_funcionalidades/`.
- [x] 1.2 Update `frontend/src/app/page.module.scss` to implement the landing hero, botanical tonal surfaces, responsive feature mosaic, CTA treatments, and footer using existing Fotosíntesis tokens and primitives.
- [x] 1.3 Adapt all public-root reference copy from `PlantCare` or unsupported placeholder behavior to accurate `Fotosíntesis` product copy and existing route destinations.
- [x] 1.4 Update `frontend/src/app/(auth)/welcome/page.tsx` so `/welcome` matches the public-entry visual language while preserving login and registration navigation.

## 2. Transactional Auth Shell

- [x] 2.1 Refactor `frontend/src/components/auth/AuthShell.tsx` to own the shared transactional auth layout: brand header, centered card region, optional supporting content, and simple footer.
- [x] 2.2 Update `frontend/src/components/auth/AuthShell.module.scss` to match the login/register reference shell using tokenized filled surfaces, low-contrast outlines, ambient elevation, responsive spacing, and Fotosíntesis typography.
- [x] 2.3 Ensure the shell keeps user-facing product naming as `Fotosíntesis` and does not introduce unsupported interactive header/footer controls.

## 3. Auth Form Presentation

- [x] 3.1 Restyle `frontend/src/components/auth/LoginForm.tsx` within the transactional shell while preserving `signIn`, `callbackUrl`, registered-success notice, neutral failure error, disabled states, field labels, and submit behavior.
- [x] 3.2 Restyle `frontend/src/components/auth/RegisterForm.tsx` within the transactional shell while preserving React Hook Form/Zod validation, API registration, duplicate/error handling, success redirect to `/login?registered=1`, field labels, and submit behavior.
- [x] 3.3 Restyle `frontend/src/components/auth/RecoveryForm.tsx` within the transactional shell while preserving recovery API submission, neutral confirmation message, validation, field label, and submit behavior.
- [x] 3.4 Keep social login, if displayed, as a disabled visual placeholder with clear disabled semantics and no real authentication attempt.

## 4. Route Integration

- [x] 4.1 Review `frontend/src/app/(auth)/login/page.tsx`, `frontend/src/app/(auth)/register/page.tsx`, and `frontend/src/app/(auth)/forgot-password/page.tsx` copy/props so each route uses the redesigned shell and accurate Fotosíntesis messaging.
- [x] 4.2 Verify unauthenticated private-route redirects still send users to `/login` with the existing callback URL behavior and are not replaced by a client-side session gate.
- [x] 4.3 Confirm no private feature page modules are redesigned or behaviorally altered by this change.

## 5. Tests And Verification

- [x] 5.1 Update or add focused component tests for login, registration, and recovery forms to cover preserved labels, submit names, validation/errors, success notice, disabled placeholder social action, and recovery confirmation.
- [x] 5.2 Update or add public/auth e2e coverage for the landing/welcome CTAs, registration-to-login success flow, login callback redirect behavior, recovery flow, and unauthenticated private-route redirect.
- [x] 5.3 Run the relevant frontend lint, type, unit, and e2e checks for public/auth surfaces and fix regressions.
- [x] 5.4 Manually inspect the redesigned public and auth pages at mobile and desktop widths for responsive layout, token consistency, and accessible form interactions.
