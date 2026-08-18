"""Backend reminder suggestion generation.

This module centralizes AI-labeled reminder suggestions so they originate
from a single backend operation grounded in confirmed taxonomy, profile
evidence, garden location, notes, active reminders, and timezone. It never
derives action intent from semantic regular expressions or fixed calendar
defaults (tomorrow, 09:00, weekly); action and schedule semantics come from
schema-validated model output.
"""

from __future__ import annotations

import asyncio
import json
from datetime import date as Date
from datetime import datetime, time as Time, timezone as dt_timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.assistant.repository import AssistantRepository
from app.assistant.tools import AssistantTools
from app.auth.tables import (
    garden_plants,
    identification_candidates,
    plant_profiles,
)
from app.knowledge.repository import KnowledgeRepository
from app.observability.logging import get_logger
from app.reminders.repository import ReminderRepository
from app.schemas.reminders import (
    ReminderClarificationResult,
    ReminderDuplicateResult,
    ReminderRecurrence,
    ReminderSuggestionEvidence,
    ReminderSuggestionOutcome,
    ReminderSuggestionRequest,
    ReminderSuggestionResult,
)
from app.scheduling.timezone import resolve_timezone

logger = get_logger(__name__)

_REQUIRED_SCHEDULE_FIELDS = ("date", "time", "timezone", "recurrence")

_ACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "description": "The proposed plant care action as a concise phrase (e.g. 'Riego', 'Fertilizante').",
        },
        "light_context_relevant": {
            "type": "boolean",
            "description": "Whether a recent light measurement for the plant can materially improve the suggestion (e.g. watering or light-dependent actions).",
        },
        "confidence": {
            "type": "number",
            "minimum": 0,
            "maximum": 1,
            "description": "Confidence that the proposed action is well grounded in the provided evidence.",
        },
        "limitations": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Bounded limitations or caveats about the suggestion.",
        },
    },
    "required": ["action", "light_context_relevant", "confidence", "limitations"],
    "additionalProperties": False,
}

_SUGGESTION_SCHEMA = {
    "type": "object",
    "properties": {
        "date": {
            "type": ["string", "null"],
            "description": "Scheduled date in YYYY-MM-DD, or null when not specified.",
        },
        "time": {
            "type": ["string", "null"],
            "description": "Scheduled time in HH:MM (24h), or null when not specified.",
        },
        "timezone": {
            "type": ["string", "null"],
            "description": "IANA timezone for the scheduled date/time, or null when not specified.",
        },
        "recurrence": {
            "type": ["string", "null"],
            "enum": [item.value for item in ReminderRecurrence],
            "description": "Explicit recurrence value, including an explicit 'none' for a one-off reminder.",
        },
        "justification": {
            "type": "string",
            "description": "A concise justification for the suggested reminder grounded in the evidence.",
        },
    },
    "required": ["date", "time", "timezone", "recurrence", "justification"],
    "additionalProperties": False,
}


class ReminderSuggestionError(ValueError):
    """Base error for the reminder suggestion operation."""


class PlantNotFoundError(ReminderSuggestionError):
    """Raised when the selected garden plant is not owned by the user."""


class ProviderFailureError(ReminderSuggestionError):
    """Raised when the assistant model cannot produce schema-validated output."""


class ReminderSuggestionService:
    """Generates evidence-grounded reminder suggestions from the backend."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self.tools = AssistantTools(
            AssistantRepository(session), KnowledgeRepository(session)
        )
        self.reminders = ReminderRepository(session)

    async def suggest(
        self,
        *,
        user_id: UUID,
        payload: ReminderSuggestionRequest,
        now: datetime | None = None,
    ) -> ReminderSuggestionOutcome:
        context = await self._load_context(user_id=user_id, garden_plant_id=payload.garden_plant_id)
        if context is None:
            raise PlantNotFoundError("Plant not found in My Garden.")

        classification = await self._classify(context, request=payload.request)
        light_facts: list[str] = []
        if classification["light_context_relevant"]:
            light_facts = await self._load_light(
                user_id=user_id, garden_plant_id=payload.garden_plant_id, now=now
            )

        suggestion = await self._generate_suggestion(
            context, classification=classification, light_facts=light_facts
        )

        missing = self._missing_schedule_fields(suggestion)
        if missing:
            _record_outcome("clarified")
            return ReminderClarificationResult(kind="clarification", missing_fields=missing)

        due = _build_due(suggestion)
        existing = await self.reminders.find_equivalent(
            user_id=user_id,
            garden_plant_id=payload.garden_plant_id,
            action=suggestion["action"],
            due_at=due,
            recurrence=suggestion["recurrence"],
        )
        if existing is not None:
            _record_outcome("duplicate")
            return ReminderDuplicateResult(
                kind="duplicate", existing_reminder_id=existing
            )

        return ReminderSuggestionResult(
            kind="suggestion",
            garden_plant_id=payload.garden_plant_id,
            plant_name=context["plant_name"],
            action=suggestion["action"],
            date=Date.fromisoformat(suggestion["date"]),
            time=Time.fromisoformat(suggestion["time"]),
            timezone=suggestion["timezone"],
            recurrence=ReminderRecurrence(suggestion["recurrence"]),
            evidence=ReminderSuggestionEvidence(
                taxonomy=context.get("taxonomy"),
                location=context.get("location"),
                notes=context.get("notes"),
                profile_sections=context.get("profile_sections", []),
                active_reminders=context.get("active_reminders", 0),
                light_context="; ".join(light_facts) if light_facts else None,
            ),
            confidence=float(classification["confidence"]),
            limitations=list(classification["limitations"]),
            justification=suggestion["justification"],
        )

    async def _load_context(self, *, user_id: UUID, garden_plant_id: UUID) -> dict | None:
        """Resolve the user's own garden plant with confirmed taxonomy, notes,
        location, profile evidence, and active reminder count."""
        row = (
            await self._session.execute(
                select(
                    garden_plants.c.nickname,
                    garden_plants.c.notes,
                    garden_plants.c.location,
                    garden_plants.c.active_reminders,
                    garden_plants.c.confirmed_candidate_id,
                    plant_profiles.c.scientific_name,
                    plant_profiles.c.common_name,
                    plant_profiles.c.sections,
                    plant_profiles.c.limitations,
                    identification_candidates.c.accepted_scientific_name,
                    identification_candidates.c.binomial_name,
                    identification_candidates.c.validation_status,
                    identification_candidates.c.confirmed_at,
                    identification_candidates.c.gbif_accepted_key,
                )
                .join(plant_profiles, plant_profiles.c.id == garden_plants.c.profile_id)
                .outerjoin(
                    identification_candidates,
                    identification_candidates.c.id
                    == garden_plants.c.confirmed_candidate_id,
                )
                .where(
                    garden_plants.c.id == garden_plant_id,
                    garden_plants.c.user_id == user_id,
                )
            )
        ).first()
        if row is None:
            return None

        nickname = row._mapping[garden_plants.c.nickname]
        common_name = row._mapping[plant_profiles.c.common_name]
        scientific_name = row._mapping[plant_profiles.c.scientific_name]
        taxonomy = scientific_name
        if (
            row._mapping[identification_candidates.c.confirmed_at] is not None
            and row._mapping[identification_candidates.c.validation_status] == "validated"
        ):
            taxonomy = (
                row._mapping[identification_candidates.c.accepted_scientific_name]
                or row._mapping[identification_candidates.c.binomial_name]
                or scientific_name
            )
        sections = row._mapping[plant_profiles.c.sections] or {}
        profile_sections: list[str] = []
        for items in sections.values():
            if isinstance(items, list):
                profile_sections.extend(str(item) for item in items if item)
        return {
            "garden_plant_id": garden_plant_id,
            "plant_name": nickname or common_name or scientific_name,
            "taxonomy": taxonomy,
            "nickname": nickname,
            "location": row._mapping[garden_plants.c.location],
            "notes": row._mapping[garden_plants.c.notes],
            "active_reminders": int(row._mapping[garden_plants.c.active_reminders] or 0),
            "profile_sections": profile_sections,
            "profile_limitations": list(row._mapping[plant_profiles.c.limitations] or []),
            "accepted_gbif_key": row._mapping[identification_candidates.c.gbif_accepted_key],
            "confirmed_binomial": row._mapping[identification_candidates.c.binomial_name],
        }

    async def _classify(self, context: dict, *, request: str | None) -> dict:
        prompt = _action_prompt(context, request=request)
        data = await self._generate_json(prompt, _ACTION_SCHEMA)
        return {
            "action": _require_non_blank(data.get("action"), "action"),
            "light_context_relevant": bool(data.get("light_context_relevant")),
            "confidence": _bounded_confidence(data.get("confidence")),
            "limitations": [str(item) for item in (data.get("limitations") or [])],
        }

    async def _load_light(
        self, *, user_id: UUID, garden_plant_id: UUID, now: datetime | None
    ) -> list[str]:
        from app.assistant.light_context import (
            is_light_measurement_eligible,
            light_context_from_measurement,
            light_reading_facts,
        )

        from app.core.settings import get_settings

        result = await self.tools.light_measurement_lookup(
            user_id=user_id, garden_plant_id=garden_plant_id
        )
        if not result.ok:
            logger.warning(
                "reminder_suggestion_light_lookup_failed",
                extra={"ctx_garden_plant_id": str(garden_plant_id)},
            )
            return []
        measurement = result.data
        if not is_light_measurement_eligible(
            measurement,
            get_settings(),
            user_id=user_id,
            garden_plant_id=garden_plant_id,
            now=now,
        ):
            return []
        return light_reading_facts(
            light_context_from_measurement(measurement, get_settings())
        )

    async def _generate_suggestion(
        self, context: dict, *, classification: dict, light_facts: list[str]
    ) -> dict:
        prompt = _suggestion_prompt(context, classification=classification, light_facts=light_facts)
        data = await self._generate_json(prompt, _SUGGESTION_SCHEMA)
        recurrence = data.get("recurrence")
        return {
            "action": classification["action"],
            "date": _clean_optional(data.get("date")),
            "time": _clean_optional(data.get("time")),
            "timezone": _clean_optional(data.get("timezone")),
            "recurrence": recurrence,
            "justification": _require_non_blank(data.get("justification"), "justification"),
        }

    async def _generate_json(self, prompt: str, schema: dict) -> dict:
        from app.core.settings import get_settings

        settings = get_settings()
        try:
            result = await asyncio.wait_for(
                self.tools.generate_json(prompt, schema, model_purpose="reminder_suggestion"),
                timeout=settings.assistant_classifier_timeout_seconds,
            )
        except TimeoutError as exc:
            raise ProviderFailureError("Suggestion generation timed out.") from exc
        if not result.ok or not isinstance(result.data, dict):
            raise ProviderFailureError(
                "The assistant could not produce a valid suggestion. Please retry."
            )
        return result.data

    def _missing_schedule_fields(self, suggestion: dict) -> list[str]:
        missing: list[str] = []
        if not suggestion["date"]:
            missing.append("date")
        if not suggestion["time"]:
            missing.append("time")
        if not suggestion["timezone"]:
            missing.append("timezone")
        if suggestion["recurrence"] not in {item.value for item in ReminderRecurrence}:
            missing.append("recurrence")
        return missing


def _build_due(suggestion: dict) -> datetime:
    zone = resolve_timezone(suggestion["timezone"])
    date = Date.fromisoformat(suggestion["date"])
    time = Time.fromisoformat(suggestion["time"])
    from app.scheduling.timezone import local_datetime_to_utc

    return local_datetime_to_utc(date, time, zone) if zone is not None else datetime.combine(
        date, time, tzinfo=dt_timezone.utc
    )


def _clean_optional(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _require_non_blank(value: object, name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ProviderFailureError(f"The assistant returned an empty {name}.")
    return text


def _bounded_confidence(value: object) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return 0.5
    return max(0.0, min(1.0, confidence))


def _action_prompt(context: dict, *, request: str | None) -> str:
    return (
        "Propose a single plant care reminder action for a user's garden plant. "
        "Return only JSON matching the schema; every required field MUST be present. "
        "Derive the action and confidence from the evidence below, not from keywords in a "
        "fixed list, and never invent a fixed default schedule.\n"
        f"Confirmed taxonomy: {context.get('taxonomy') or 'missing'}\n"
        f"Display name: {context.get('nickname') or context.get('plant_name') or 'missing'}\n"
        f"Location: {context.get('location') or 'not set'}\n"
        f"User notes: {context.get('notes') or 'none'}\n"
        f"Active reminders for this plant: {context.get('active_reminders', 0)}\n"
        f"Profile care guidance: {_json(context.get('profile_sections') or [])}\n"
        f"User request: {request or 'no explicit request'}"
    )


def _suggestion_prompt(
    context: dict, *, classification: dict, light_facts: list[str]
) -> str:
    light_clause = (
        f"Eligible light measurement: {'; '.join(light_facts)}." if light_facts else ""
    )
    return (
        "Complete a reminder suggestion for a garden plant. Return only JSON matching the "
        "schema; every required field MUST be present, using null for fields that are not "
        "specified. Never invent tomorrow as the date, 09:00 as the time, or weekly as the "
        "default recurrence. If the user has not provided an explicit date, time, timezone, "
        "or recurrence, leave that field null so the caller can ask for clarification. "
        "Always set recurrence to an explicit value when known, including 'none' for a "
        "one-off reminder.\n"
        f"Confirmed taxonomy: {context.get('taxonomy') or 'missing'}\n"
        f"Display name: {context.get('nickname') or context.get('plant_name') or 'missing'}\n"
        f"Location: {context.get('location') or 'not set'}\n"
        f"User notes: {context.get('notes') or 'none'}\n"
        f"Proposed action: {classification.get('action')}\n"
        f"Profile care guidance: {_json(context.get('profile_sections') or [])}\n"
        f"{light_clause}\n"
        "Justification must be concise and grounded in the evidence above."
    )


def _json(value: object) -> str:
    try:
        return json.dumps(value, ensure_ascii=False)
    except (TypeError, ValueError):
        return "[]"


def _record_outcome(outcome: str) -> None:
    from app.observability.metrics import metrics_registry

    metrics_registry.record_reminder_suggestion_outcome(outcome=outcome)
