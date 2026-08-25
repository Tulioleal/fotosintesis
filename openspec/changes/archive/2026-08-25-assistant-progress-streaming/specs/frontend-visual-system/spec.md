## MODIFIED Requirements
### Requirement: Assistant experience applies Fotosíntesis foundation

The `/assistant` experience SHALL apply the archived Fotosíntesis visual foundation to the assistant layout, plant context sidebar, message stream, composer, supporting cards, and state treatments. When a server-authored stage stream is active, the pending treatment SHALL present live stage labels and progress within the same Fotosíntesis state language, replacing the static pending copy without introducing a competing visual system.

#### Scenario: Pending state renders live stages

- WHEN a chat turn streams server-authored stage events
- THEN the pending region shows the current stage label and bounded progress treatment using Fotosíntesis tokens and typography
- AND the rotating client-side stopgap copy is not displayed while the stream is active

#### Scenario: Fallback retains the established pending treatment

- WHEN streaming is unavailable, disabled, or fails mid-turn
- THEN the pending region falls back to the existing Fotosíntesis pending copy and treatment without layout drift
