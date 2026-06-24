## ADDED Requirements

### Requirement: User-facing plant naming in response prose

The assistant SHALL address the plant in user-facing response prose using
the value in `display_plant_name` (the nickname or display name supplied
via the `plant` request field, or the saved-plant's nickname from the
selected garden plant when the request does not provide one). The
operational, scientific, and binomial plant names MUST be treated as
retrieval and taxonomy context only and MUST NOT replace the display
name as the leading plant name in the prose. This requirement applies
to the grounded answer prompt, the disclaimed general-guidance prompt,
the conservative safety fallback, the simple fallback draft, and the
recovery draft for answer generation. The display-name priority MUST
remain `request.plant -> request.plant_scientific_name ->
request.plant_binomial_name`, then the saved-plant's nickname from the
selected garden plant, then the operational name. The classifier's
`plant_reference` field MUST continue to carry the nickname as a
reference signal only and MUST NOT be sent to investigation operations.

#### Scenario: Nickname is used in grounded-answer response prose

- **WHEN** the assistant returns a grounded plant-care answer and a
  `display_plant_name` (nickname) is available
- **THEN** the user-facing prose refers to the plant using the
  `display_plant_name` value
- **AND** the prose does not substitute the common name, the
  scientific name, or the binomial from the evidence, taxonomy
  context, or source metadata as the leading plant name
- **AND** the `display_plant_name` value remains the leading plant
  name across continuous narrative prose

#### Scenario: Nickname is used in disclaimed-guidance response prose

- **WHEN** the assistant returns a `general_guidance_with_disclaimer`
  answer and a `display_plant_name` (nickname) is available
- **THEN** the four user-facing sections (`What sources validated`,
  `What sources did not validate`, `General unvalidated guidance`,
  `Details that would help`) refer to the plant using the
  `display_plant_name` value
- **AND** the prose does not substitute the common name, the
  scientific name, or the binomial as the leading plant name
- **AND** the `display_plant_name` value remains the leading plant
  name in each section

#### Scenario: Nickname is used in conservative safety fallback response prose

- **WHEN** the conservative safety fallback renders a pet-safety,
  edibility, or generic safety response and a `display_plant_name`
  (nickname) is available
- **THEN** the rendered prose refers to the plant using the
  `display_plant_name` value
- **AND** the prose does not substitute the common name, the
  scientific name, or the binomial as the leading plant name

#### Scenario: Nickname is used in simple fallback draft response prose

- **WHEN** the assistant renders a simple fallback draft (missing
  plant context, ambiguous plant, out of domain, tool action failed,
  reminder confirmation, reminder creation, reminder failure, and
  similar fallback paths) and a `display_plant_name` (nickname) is
  available
- **THEN** the rendered prose refers to the plant using the
  `display_plant_name` value
- **AND** the prose does not substitute the common name, the
  scientific name, or the binomial as the leading plant name

#### Scenario: Nickname is used in recovery draft response prose

- **WHEN** the assistant renders a recovery draft after a recoverable
  answer-generation failure and a `display_plant_name` (nickname) is
  available
- **THEN** the recovered prose refers to the plant using the
  `display_plant_name` value
- **AND** the prose does not substitute the common name, the
  scientific name, or the binomial as the leading plant name

#### Scenario: Display name is not used for investigation operations

- **WHEN** the assistant chat request includes a `display_plant_name`
  (nickname) and a confirmed operational plant name (binomial or
  scientific)
- **THEN** `knowledge_search`, `trusted_web_search`,
  `plant_data_lookup`, embedding calls, indexing calls, and
  ingestion queries continue to use the operational plant name
- **AND** the `display_plant_name` (nickname) is NOT sent to any
  investigation operation
- **AND** the classifier's `plant_reference` field is treated as a
  reference signal only and is NOT used for retrieval, web search,
  or ingestion
- **AND** the assistant's diagnostic metadata records the
  operational plant name used for investigation without exposing the
  nickname as botanical source evidence

#### Scenario: Display name is absent falls back gracefully with English placeholder

- **WHEN** the assistant chat request omits `display_plant_name`
  (nickname) and no saved-plant nickname is available from the
  selected garden plant
- **THEN** the user-facing prose MAY use a generic English reference
  (e.g. "your plant", "not specified")
- **AND** the model receives a language-neutral English placeholder
  in the prompt, never a Spanish phrase like "esta planta" or
  "no especificada"
- **AND** the LLM translates the placeholder to the `answer_language`
  naturally
- **AND** the investigation operations continue to use the
  operational name as before
