## 1. Baseline Review

- [x] 1.1 Review `frontend/REFERENCES/fotosintesis/DESIGN.md`, `frontend/REFERENCES/recordatorios/screen.png`, and `frontend/REFERENCES/recordatorios/code.html` before editing.
- [x] 1.2 Inspect the current reminders and light-meter components, tests, and route links from garden, profile, assistant, and the private shell.
- [x] 1.3 Identify any existing shared Fotosíntesis primitives or care-action styles that can be reused without broad refactoring.

## 2. Reminders Redesign

- [x] 2.1 Update `/reminders` route and `RemindersManager.tsx` to match the reference split layout with page title, new-reminder form, AI suggestion card, and reminder list area.
- [x] 2.2 Restyle reminder form controls, recurrence choices, validation/help messages, notification permission messaging, and save action with Fotosíntesis tokens while preserving labels, accessible names, and submission behavior.
- [x] 2.3 Restyle reminder rows or cards, plant metadata, pending/completed states, update/delete/complete actions, recurring indicators, loading states, empty states, and error states without changing API behavior.
- [x] 2.4 Replace or adapt any copied `PlantCare` or static reference copy with `Fotosíntesis` or accurate current reminders copy.
- [x] 2.5 Ensure reminders remain responsive, with the reference desktop layout at the verification viewport and readable stacked behavior on smaller screens.

## 3. Light Meter Redesign

- [x] 3.1 Update `/light-meter`, `LightMeter.tsx`, and `LightMeter.module.scss` to use a Fotosíntesis measurement-first care-tool layout.
- [x] 3.2 Restyle the primary measurement action area, ambient-light sensor status, camera fallback status, manual classification controls, and guidance notices while preserving all measurement attempts and fallback behavior.
- [x] 3.3 Restyle reading results, reliability messaging, unreliable camera blocking, garden plant association, persistence errors, and save action while preserving save eligibility and API behavior.
- [x] 3.4 Ensure the light-meter layout works inside the private shell on desktop and mobile without conflicting with existing navigation.

## 4. Cross-Feature Integration

- [x] 4.1 Verify garden, profile, assistant, and private shell links to `/reminders` and `/light-meter` still resolve and preserve existing route behavior.
- [x] 4.2 Avoid visual changes to unrelated garden, profile, assistant, identification, public/auth, or shell screens except for minimal link-validity fixes if needed.
- [x] 4.3 Document any intentional visual deviation from the reminders reference screenshot or derived light-meter care-tool pattern with the reason.

## 5. Tests and Verification

- [x] 5.1 Update reminders component tests only where necessary for the visual structure while preserving lifecycle, validation, notification, recurrence, and AI suggestion behavior assertions.
- [x] 5.2 Update light-meter component tests only where necessary for the visual structure while preserving sensor, camera fallback, manual classification, reliability, association, and persistence behavior assertions.
- [x] 5.3 Run relevant reminders and light-meter component tests.
- [x] 5.4 Run relevant reminders and light-meter e2e journey tests. (Done via the new deterministic `e2e/care-tools.spec.ts` suite: 4/4 pass against the local Docker stack with no vision/LLM provider dependency. Pre-existing `mvp-journeys.spec.ts` journeys are kept as the broader-MVP suite; their 3 vision/LLM-dependent failures are out of scope. See verification-notes.md "Deterministic care-tools E2E" section.)
- [x] 5.5 Manually compare `/reminders` against `frontend/REFERENCES/recordatorios/screen.png` using the defined desktop verification state and same viewport class. (Done: authenticated screenshots at 1440x900 and 390x844 captured against the seeded state — see `verification/reminders-1440x900.png` and `verification/reminders-390x844.png`. Desktop screenshot also shows the row action trigger visible by default on every row.)
- [x] 5.6 Manually verify `/light-meter` using the defined care-tool verification state, including measurement action, manual fallback, sensor/camera status, prepared reading result, reliability messaging, optional plant association, and save action. (Done: authenticated screenshots at 1440x900 and 390x844 captured with a prepared manual "Alta" reading — see `verification/light-meter-1440x900.png` and `verification/light-meter-390x844.png`. The deterministic e2e also exercises the manual reading + save flow end-to-end.)
