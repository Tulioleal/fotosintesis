## Context

The archived Fotosíntesis foundation defines the Clean Botanical visual language: warm paper surfaces, forest-green primary actions, soil-brown accents, tonal sage containers, Bodoni Moda headlines, Roboto functional text, rounded cards, soft outlines, and ambient green-tinted elevation. The private shell and Home dashboard already use this direction, but public and transactional authentication routes still use a simpler shell and the public root remains a foundation proof page rather than a cohesive entry experience.

This change applies the same visual foundation to unauthenticated entry surfaces only. The relevant implementation files live under `frontend/src/...` even when referenced in product shorthand as `src/...`.

## Goals / Non-Goals

**Goals:**

- Redesign the public root and `/welcome` entry experience around the `bienvenida_con_funcionalidades` reference while adapting placeholder copy to Fotosíntesis.
- Redesign `/login` and `/register` around their transactional reference pages while preserving form behavior, validation, redirects, accessible labels, and registration success flow.
- Keep `/forgot-password` in the same transactional visual family when the route remains available.
- Reuse the archived visual-system tokens, fonts, primitives, and icon strategy instead of introducing one-off colors, type, shadows, or brand treatments.
- Keep automated auth and e2e tests stable by preserving accessible field labels and action names unless visible copy is intentionally updated in specs.

**Non-Goals:**

- No private feature page redesigns beyond avoiding regressions in unauthenticated redirects into private routes.
- No changes to Auth.js/NextAuth ownership, session persistence, callback URL handling, backend registration, recovery token generation, or API contracts.
- No new social authentication implementation; social login remains a disabled visual placeholder if shown.
- No new semantic plant-care logic, classifier behavior, RAG behavior, or botanical keyword heuristics.

## Decisions

### Decision 1: Treat the public root and `/welcome` as one entry system

The public root should become the broad marketing/entry surface using the welcome-with-features reference: sticky/simple brand header, editorial hero, clear login/register CTAs, feature mosaic, and footer. `/welcome` should remain an auth-flow route but reuse the same art direction at a smaller scope so routes that already point there continue to feel cohesive.

Alternative considered: keep `src/app/page.tsx` as a visual-foundation demo. This was rejected because the foundation is archived and unauthenticated users now need a product entry screen, not an internal token showcase.

### Decision 2: Centralize transactional auth chrome in `AuthShell`

`AuthShell` should own the shared transactional layout from the login/register references: minimal brand header, centered surface card, tokenized filled field treatments, ambient elevation, and simple footer. Login, register, and recovery pages should vary copy and form content through props/children rather than each page recreating shell structure.

Alternative considered: style each auth page independently. This was rejected because it risks visual drift and makes recovery harder to keep aligned with login/register.

### Decision 3: Preserve form semantics before visual fidelity

Forms may add decorative icons, helper copy, success notices, and tokenized wrappers, but they must keep React Hook Form/Zod wiring, disabled submit states, form error handling, field registration, callback URL redirect behavior, and current accessible labels/button names used by tests. If a button's visible copy changes for design reasons, tests must be updated only when the spec explicitly expects the new copy.

Alternative considered: port reference markup directly. This was rejected because the references are static mockups and do not include the real validation, session, callback, or recovery behavior.

### Decision 4: Adapt reference copy, not behavior

Reference copy such as `PlantCare`, generic English footer links, inactive search/notification controls, and unsupported feature promises should be rewritten to `Fotosíntesis` and current product capabilities. The visual intent can remain, but unsupported interactive controls should be omitted, disabled with clear semantics, or linked only to existing auth routes.

Alternative considered: copy the reference content verbatim. This was rejected because it would expose placeholder product names and imply features or navigation that are not implemented.

### Decision 5: Keep styling tokenized and local to public/auth surfaces

Public and auth SCSS modules should consume existing CSS custom properties/SCSS tokens and shared primitives where they fit. New layout classes should be scoped to `page.module.scss` or `AuthShell.module.scss`; global style changes should be limited to missing reusable tokens or utilities required by the visual-system contract.

Alternative considered: add a new page-specific design system. This was rejected because the archived foundation is the required baseline.

## Risks / Trade-offs

- **Risk: Static references suggest unsupported navigation or feature depth.** -> Mitigation: preserve visual rhythm while linking only to existing auth/public routes and using accurate Fotosíntesis copy.
- **Risk: Auth tests break due to renamed accessible controls.** -> Mitigation: preserve existing form labels and primary button names unless a spec scenario explicitly updates them; adjust tests only for intentional presentation expectations.
- **Risk: Callback URL or registration success flow regresses during visual refactor.** -> Mitigation: keep `LoginForm`, `RegisterForm`, and `RecoveryForm` submit logic intact and add/retain tests around redirects and success notices.
- **Risk: Public redesign bleeds into private features.** -> Mitigation: limit touched routes/components to public/auth surfaces and relevant tests; do not alter private feature page modules.
- **Risk: Reference imagery cannot be used as remote production assets.** -> Mitigation: prefer existing shared icons, gradients, tonal botanical shapes, or approved local/static assets; do not depend on opaque generated reference image URLs.

## Migration Plan

1. Replace the public root foundation proof page with the Fotosíntesis landing structure and tokenized SCSS adapted from the welcome-with-features reference.
2. Update `/welcome` to use the same public-entry visual language while preserving its current login/register navigation purpose.
3. Refactor `AuthShell` and its SCSS module into the shared transactional shell for login, register, and recovery routes.
4. Restyle `LoginForm`, `RegisterForm`, and `RecoveryForm` fields, notices, actions, and disabled social placeholders without changing submit logic or validation schemas.
5. Update focused component and e2e tests for the new public/auth presentation while preserving behavior assertions.
6. Run frontend lint/type/unit/e2e checks appropriate for touched public/auth flows.

Rollback is source-only: revert frontend route, auth component, style, and test changes. No data migration, API migration, or persisted session migration is involved.

## Open Questions

No blocking open questions remain. During implementation, use local/tokenized botanical illustration treatments if reference remote images are not appropriate to ship.
