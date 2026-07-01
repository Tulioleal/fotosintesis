## Context

The Fotosíntesis visual foundation, authenticated shell/home redesign, and public/auth redesign are already archived. The `/identify` screen is now the next high-value private journey to align with that foundation because it is the entry point for plant identification, candidate confirmation, profile creation, and assistant context.

The current `IdentifyFlow` already owns the required functional behavior: camera permission probing and upload fallback, file upload through `/api/identifications`, preview rendering, loading state, candidate rendering, GBIF validation gating, confirmation requests, and post-confirmation profile/assistant links. This change should preserve those behaviors and focus on state-specific visual composition.

The implementation will use these references as state baselines:

- Initial upload/camera entry: `frontend/REFERENCES/identificando_planta_2/screen.png` and `frontend/REFERENCES/identificando_planta_2/code.html`.
- Analyzing/loading: `frontend/REFERENCES/identificando_planta_1/screen.png` and `frontend/REFERENCES/identificando_planta_1/code.html`.
- Results: `frontend/REFERENCES/resultados_de_identificaci_n/screen.png` and `frontend/REFERENCES/resultados_de_identificaci_n/code.html`.

## Goals / Non-Goals

**Goals:**

- Redesign `/identify` across initial, camera fallback notice, preview, analyzing, error, results, and confirmed-candidate states using the archived Fotosíntesis tokens and visual language.
- Adapt the references into the existing private shell rather than duplicating static reference headers, footers, or navigation.
- Preserve existing accessible button/link names and route behavior relied on by unit and e2e tests unless the spec explicitly updates visible copy.
- Keep the upload/camera behavior, `/api/identifications` flow, candidate confirmation contract, GBIF validation gate, and post-confirmation links behaviorally unchanged.
- Ensure placeholder reference copy such as `PlantCare` is replaced with accurate `Fotosíntesis` product copy.

**Non-Goals:**

- Redesigning garden, profile, assistant, reminders, or shell navigation screens.
- Changing the identification backend, candidate ranking, GBIF validation, profile generation, or assistant query semantics.
- Introducing new image-processing, drag-and-drop upload behavior, or manual search unless already supported by the current flow.
- Replacing the existing API route or changing persisted identification data.

## Decisions

1. Keep `IdentifyFlow` as the state owner and redesign its markup/styles in place.

   Rationale: The component already contains the file inputs, state transitions, API calls, confirmation mutation, and link generation that must be preserved. Rewriting the flow as a new component would increase regression risk without adding architectural value.

   Alternative considered: split every state into new subcomponents. This could improve readability later, but it is not required for a scoped visual redesign and could obscure behavior preservation.

2. Treat reference headers, footers, and navigation as visual context only.

   Rationale: The authenticated private shell already provides app navigation. The identification screen should adapt the reference content rhythm, upload panel, preview media well, progress treatment, and result-card grid without embedding duplicate static shell elements or unsupported links.

   Alternative considered: copy the reference page structure wholesale. This would conflict with the archived private shell and could introduce placeholder navigation/copy.

3. Preserve stable accessible names for tested controls and links.

   Rationale: Existing unit and e2e tests use `Tomar foto`, `Subir imagen`, `Confirmar candidata validada`, `Ver perfil y agregar a Mi Jardin`, and `Preguntar al asistente` as behavioral anchors. Visual changes can add surrounding labels, hints, chips, or icons, but should not rename these controls unless tests and specs deliberately change the product copy.

   Alternative considered: update all copy to match the references exactly. The references include placeholder product language and generic actions that do not fully match current behavior.

4. Use tokenized CSS modules and existing shared visual-system primitives where practical.

   Rationale: The visual-system spec requires Fotosíntesis colors, typography, spacing, radii, surfaces, outlines, and low-contrast elevation. `IdentifyFlow.module.scss` should consume those tokens/custom properties and avoid a separate palette or arbitrary heavy shadows.

   Alternative considered: import Tailwind-style classes from the reference HTML. This app uses CSS modules for the current component, and copying Tailwind markup would bypass the established styling approach.

5. Represent loading as a real state over the selected preview.

   Rationale: The analyzing reference uses a muted image preview, scan/progress treatment, and candidate skeletons. The implementation can reuse the selected object URL for the media area while `isSubmitting` is true and render decorative scanning/skeleton UI without changing API timing or cancellation behavior.

   Alternative considered: use a static placeholder image from the reference. That would disconnect the loading state from the user's submitted image and risk external image dependencies.

## Risks / Trade-offs

- Visual copy drift could break tests → Preserve existing accessible names for controls and links, and update tests only for intentional new state assertions.
- Reference mockups contain `PlantCare` and unsupported static navigation → Treat those as placeholders and adapt only the visual intent into Fotosíntesis copy and real routes.
- A richer visual state could accidentally alter behavior → Keep upload inputs, fetch calls, confirmation guard, and link-building logic intact; add tests around any markup changes that affect query selectors.
- Loading skeletons and animation may affect accessibility → Mark decorative animation appropriately, keep the text loading status visible, and respect existing button labels and image alt text.
- Candidate cards may become visually denser on mobile → Use the archived responsive grid rules and collapse result cards to one column at mobile widths.
