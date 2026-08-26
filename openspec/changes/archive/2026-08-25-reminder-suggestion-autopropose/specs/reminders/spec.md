## MODIFIED Requirements

### Requirement: Timezone-aware scheduling

The system SHALL resolve every reminder schedule in an effective IANA timezone taken from the reminder override when present, otherwise from the stored user timezone, and SHALL reject creation without any resolvable timezone. The creation interface SHALL treat the stored user timezone as the default and MAY expose a per-reminder override as an advanced option; the override MUST NOT be a required field.

#### Scenario: Creation uses the account timezone by default

- **WHEN** a user creates a reminder without selecting a timezone
- **THEN** the schedule resolves in the stored user timezone

#### Scenario: Override remains available as an advanced option

- **WHEN** the creation or edit form exposes the timezone control
- **THEN** it is presented as optional and collapsed behind advanced options on the create form
