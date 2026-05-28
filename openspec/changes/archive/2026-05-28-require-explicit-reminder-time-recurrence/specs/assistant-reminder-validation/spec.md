## ADDED Requirements

### Requirement: Explicit assistant reminder schedule

The assistant SHALL create plant-care reminders only when the user request includes a selected plant, a reminder action, an explicit due date, an explicit due time and an explicit recurrence.

#### Scenario: Reminder request missing explicit time

- **WHEN** the user asks the assistant to create a reminder with a date and recurrence but no explicit time
- **THEN** the assistant asks for the missing time before creating the reminder

#### Scenario: Reminder request missing recurrence

- **WHEN** the user asks the assistant to create a reminder with a plant, action, date and time but no recurrence
- **THEN** the assistant asks for the missing recurrence before creating the reminder

#### Scenario: Complete reminder request

- **WHEN** the user asks the assistant to create a reminder with plant, action, date, time and recurrence
- **THEN** the assistant calls the reminder creation tool with the explicit due timestamp and recurrence
