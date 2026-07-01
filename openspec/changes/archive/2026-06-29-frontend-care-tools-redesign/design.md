## Context

The archived Fotosíntesis visual foundation is the required baseline for private shell/home, public/auth, identification, garden/profile, and assistant experiences. The remaining care tools, `/reminders` and `/light-meter`, must now join that same visual family without changing their existing behavior contracts.

The reminders reference is explicit: `frontend/REFERENCES/recordatorios/screen.png` and `frontend/REFERENCES/recordatorios/code.html` define a desktop care-tool layout with a page title, left-column reminder form, AI suggestions card, and right-column reminder list with tonal rows, compact plant imagery, status/action affordances, botanical typography, and tokenized fields. The reference includes placeholder `PlantCare` copy that must be adapted to `Fotosíntesis` or accurate current app copy.

The light meter has no dedicated screenshot. Its redesign should use the same Fotosíntesis care-tool language: breathable private-shell page structure, tonal card hierarchy, clear action area, status/notice treatments, manual fallback controls, reliability messaging, garden plant association, and save affordance. The visual source of truth is the archived foundation plus already-redesigned plant detail and care-action surfaces.

Target reminders visual verification state before implementation:

- Viewport class: the same desktop browser/device class used to compare against `frontend/REFERENCES/recordatorios/screen.png`.
- Route/state: `/reminders` with at least one saved garden plant available for form selection.
- Form content: the new-reminder form is visible with plant, action/task, date, time, recurrence controls, validation/help treatment available, and the primary save action visible.
- AI suggestion content: a visible suggestion panel/card includes assistant-suggested reminder content or an equivalent mocked suggestion state with an acceptance action.
- Reminder list content: multiple reminders are visible, including pending reminders, at least one completed or completion-capable state where feasible, and update/delete/complete action affordances.
- Notification messaging: permission fallback messaging remains available in the same visual language when that state is triggered.
- Verification rule: mocked or seeded data should approximate the reference state; dynamic text, dates, plant names, or API timing differences cannot justify structural, spacing, typography, color, card/table hierarchy, or responsive drift.

Target light-meter visual verification state before implementation:

- Viewport class: desktop and mobile checks inside the private shell, using the same responsive margin/gutter rules as other Fotosíntesis private surfaces.
- Initial area: the primary measurement action area is visible before a reading is taken.
- Fallback area: manual registration/classification controls are visible or reachable, with camera/sensor status messaging represented.
- Reading result: a prepared reading result is visible, including lux or classification, reliability state, and clear guidance when reliability is low.
- Camera blocking: camera reliability blocking remains visible when the reading is covered, overexposed, or inconsistent.
- Garden association: optional garden plant association is visible when plants are available.
- Save flow: the save action is visible and disabled/blocked only according to the current behavior rules.

Intentional reference adaptations:

- Replace visible `PlantCare` copy from the reminders reference with `Fotosíntesis` or route-specific current copy.
- Use the existing private shell navigation instead of duplicating static reference top/bottom navigation if doing so would conflict with live shell behavior.
- Preserve current form labels, accessible names, button names, and test anchors unless a spec-level copy update is required for product naming or reference adaptation.
- Keep live reminder and light-meter API behavior unchanged, even when reference markup presents static-only controls.

## Goals / Non-Goals

**Goals:**

- Apply the archived Fotosíntesis tokens, typography, surfaces, outlines, radii, spacing, icon strategy, and low-contrast elevation to reminders and light meter.
- Make `/reminders` visually follow the provided reminders reference in structure, spacing, typography, color, form treatment, card/list hierarchy, actions, and responsive behavior at the defined verification viewport and state.
- Make `/light-meter` feel like a first-class Fotosíntesis care tool by aligning its cards, actions, status messages, reliability treatments, plant association, and save flow with the foundation and care-action surfaces.
- Preserve reminders behavior: listing, creation, update, completion, deletion, recurring behavior, validation errors, notification permission messaging, and AI suggestion acceptance.
- Preserve light meter behavior: AmbientLightSensor attempts, camera fallback, manual classification, reliability states, camera reliability blocking, garden plant association, and measurement persistence.
- Preserve existing route behavior and cross-feature links from garden, profile, assistant, and private shell surfaces.
- Document any intentional visual deviations from the reminders screenshot or derived light-meter care-tool pattern before the change is considered complete.

**Non-Goals:**

- No backend API, database, validation, reminder recurrence, notification, assistant suggestion, or measurement persistence changes.
- No redesign of unrelated garden, profile, assistant, identification, public/auth, or private shell screens beyond keeping links valid.
- No new semantic botanical classification, language detection, retrieval, or answerability behavior.
- No new deterministic keyword lists, translated word lists, regex language detection, or English/Spanish-only heuristics for plant-care semantics.
- No replacement of current behavior tests with visual-only assertions.

## Decisions

### Decision: Treat care tools as a frontend visual-system delta

Implement the change as an addition to the existing `frontend-visual-system` capability while relying on the current `reminders` and `light-meter` specs for behavior.

Rationale: The requested outcome changes presentation and verification expectations, not data contracts or domain behavior. Keeping behavior specs unchanged reduces risk of accidental API or lifecycle changes.

Alternative considered: Modify `reminders` and `light-meter` requirements directly. This would blur visual acceptance criteria with already-specified lifecycle and persistence behavior.

### Decision: Keep behavior state in the existing feature components

Redesign primarily inside `RemindersManager.tsx`, `LightMeter.tsx`, `LightMeter.module.scss`, and route-level wrappers, with shared primitives only when they reduce duplicated card/form/action styling.

Rationale: Both tools already own meaningful state and side effects. A visual redesign should not introduce new state containers or route contracts unless implementation shows a clear need.

Alternative considered: Extract a new care-tool framework before redesigning. That would add abstraction before there are enough care-tool variants to prove it is useful.

### Decision: Use a common care-tool page rhythm with feature-specific centers of gravity

Reminders should use the reference split layout: form and AI suggestions in a narrower left column, active reminder list in the wider right column, and responsive stacking on smaller screens. Light meter should use the same tonal page rhythm but emphasize the measurement action/result area first, with fallback/manual controls and plant-save context as supporting cards.

Rationale: Reminders has a concrete screenshot, while light meter needs visual coherence rather than forced table/list mimicry.

Alternative considered: Make light meter match the reminders two-column structure exactly. This would likely obscure the measurement-first workflow and create a layout that looks related but functions poorly.

### Decision: Preserve accessible names and current form labels by default

Visual wrappers, icons, chips, and card hierarchy can change, but labels, button names, role semantics, and route targets should remain stable unless product naming or reference adaptation explicitly requires a copy change.

Rationale: The user explicitly requires behavior and test expectations to remain stable. Accessibility affordances are also part of the current contract.

Alternative considered: Rename controls to match the static reference. That would increase visual fidelity but risks breaking tests and existing user expectations without a product reason.

### Decision: Document visual deviations as verification notes

Any intentional deviation from `frontend/REFERENCES/recordatorios/screen.png` or from the derived light-meter care-tool pattern should be recorded in the implementation verification notes or design follow-up with a reason.

Rationale: The reference includes static navigation, placeholder brand copy, and mocked data that cannot be copied blindly into the live app. Explicit deviation notes keep visual acceptance objective.

Alternative considered: Allow implementation comments or PR discussion to explain deviations informally. That makes acceptance harder to audit later.

## Risks / Trade-offs

- [Risk] The private shell may constrain exact screenshot fidelity for headers, navigation, or mobile bottom spacing. → Mitigation: keep the care-tool content faithful to the reference and document shell-driven deviations.
- [Risk] Dynamic reminder data may not naturally match the reference density. → Mitigation: use seeded, mocked, or test data that approximates the visual verification state instead of accepting layout drift.
- [Risk] Restyling form controls could break validation messaging or accessible label associations. → Mitigation: preserve existing form control IDs, labels, names, and error rendering semantics while changing visual containers.
- [Risk] Light meter reliability states are behaviorally complex and can be hidden by a card-first redesign. → Mitigation: make sensor/camera/manual status, reliability guidance, blocking states, association, and save eligibility explicit verification targets.
- [Risk] Shared primitive extraction may grow scope. → Mitigation: only extract or extend primitives when it materially reduces duplication across the two care tools.

## Migration Plan

- Implement behind the existing `/reminders` and `/light-meter` routes; no data migration is required.
- Update component tests for visual structure only where necessary while preserving behavior assertions.
- Run reminders component tests, light-meter component tests, and relevant reminders/light-meter e2e journeys.
- Manually compare `/reminders` against `frontend/REFERENCES/recordatorios/screen.png` using the defined desktop verification state and viewport class.
- Manually verify `/light-meter` against the derived Fotosíntesis care-tool pattern using the defined measurement, fallback, reliability, association, and save states.
- Rollback strategy: revert the frontend route/component/style changes; no persisted data or backend contract changes are introduced.

## Open Questions

- None currently blocking implementation. If exact reference viewport dimensions are not encoded in metadata, use the same desktop viewport class selected for the screenshot comparison and record it in implementation verification notes.
