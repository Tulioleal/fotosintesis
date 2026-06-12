## ADDED Requirements

### Requirement: Gemini-backed plant vision compatibility
The system SHALL allow the vision provider interface to be backed by Gemini while preserving the existing plant identification candidate contract.

#### Scenario: Gemini vision returns plant candidates
- **WHEN** a usable identification image is analyzed with the configured vision provider set to Gemini
- **THEN** the backend returns up to three possible plant candidates with common name, suggested scientific name, visible traits and confidence high, medium, low or inconclusive

#### Scenario: Gemini vision output uses internal result types
- **WHEN** Gemini produces a structured plant-identification response
- **THEN** the provider maps the response into the existing internal image analysis result and plant candidate types without exposing Gemini SDK response types to identification domain code
