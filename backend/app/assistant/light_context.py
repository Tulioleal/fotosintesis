from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.core.settings import Settings

SUPPORTED_LIGHT_SOURCES = frozenset({"sensor", "camera", "manual"})

RELIABILITY_RANK = {"low": 0, "medium": 1, "high": 2}

_SOURCE_FRESHNESS_FIELDS = {
    "sensor": "light_measurement_freshness_sensor_days",
    "camera": "light_measurement_freshness_camera_days",
    "manual": "light_measurement_freshness_manual_days",
}


def _reliability_rank(value: Any) -> int | None:
    if value not in RELIABILITY_RANK:
        return None
    return RELIABILITY_RANK[value]


def _min_reliability_rank(settings: Settings) -> int:
    return RELIABILITY_RANK.get(
        settings.light_measurement_min_reliability, RELIABILITY_RANK["medium"]
    )


def _freshness_days(settings: Settings, source: str) -> int:
    field = _SOURCE_FRESHNESS_FIELDS.get(source)
    if field is None:
        return settings.light_measurement_freshness_default_days
    return int(getattr(settings, field))


def _to_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def is_light_measurement_eligible(
    measurement: dict | None,
    settings: Settings,
    *,
    user_id: Any = None,
    garden_plant_id: Any = None,
    now: datetime | None = None,
) -> bool:
    """A single eligibility check for recommendation use of a persisted reading.

    Covers owner and selected-plant scope, supported source, interpretable
    value, minimum reliability, and per-source freshness.
    """
    if not isinstance(measurement, dict):
        return False
    if user_id is not None and measurement.get("user_id") != user_id:
        return False
    if garden_plant_id is not None and measurement.get("garden_plant_id") != garden_plant_id:
        return False
    source = measurement.get("source")
    if source not in SUPPORTED_LIGHT_SOURCES:
        return False
    if measurement.get("classification") is None and measurement.get("lux") is None:
        return False
    rank = _reliability_rank(measurement.get("reliability"))
    if rank is None or rank < _min_reliability_rank(settings):
        return False
    measured_at = measurement.get("measured_at")
    if not isinstance(measured_at, datetime):
        return False
    reference = now or datetime.now(UTC)
    age_days = (reference - _to_aware_utc(measured_at)).total_seconds() / 86400.0
    return age_days <= _freshness_days(settings, source)


def light_context_from_measurement(
    measurement: dict,
    settings: Settings,
    *,
    now: datetime | None = None,
) -> dict:
    """Build the bounded retained measurement shape for assistant state."""
    measured_at = measurement.get("measured_at")
    reference = now or datetime.now(UTC)
    age_days = None
    if isinstance(measured_at, datetime):
        age_days = max(0.0, (reference - _to_aware_utc(measured_at)).total_seconds() / 86400.0)
    return {
        "classification": measurement.get("classification"),
        "lux": measurement.get("lux"),
        "source": measurement.get("source"),
        "measured_at": measured_at.isoformat() if isinstance(measured_at, datetime) else None,
        "age_days": age_days,
        "reliability": measurement.get("reliability"),
        "approximate": measurement.get("source") == "camera",
    }


def light_reading_facts(context: dict | None) -> list[str]:
    """Bounded, user-facing facts for a retained light measurement."""
    if not isinstance(context, dict):
        return []
    parts = []
    if context.get("classification"):
        parts.append(f"Classification: {context.get('classification')}")
    if context.get("lux") is not None:
        parts.append(f"Value: {context.get('lux')} lux")
    parts.append(f"Source: {context.get('source') or 'unknown'}")
    if context.get("measured_at"):
        parts.append(f"Measured: {context.get('measured_at')}")
    if context.get("age_days") is not None:
        parts.append(f"Age: {round(context['age_days'], 1)} days")
    parts.append(f"Reliability: {context.get('reliability') or 'unknown'}")
    if context.get("approximate"):
        parts.append("Approximate reading (camera-derived).")
    return parts


def light_context_observation_text(state) -> str:
    """Contextual observation text for answer synthesis, kept distinct from
    species-level evidence. Returns an empty string when light is irrelevant."""
    if not state.get("light_context_relevant"):
        return ""
    context = state.get("light_context")
    if isinstance(context, dict):
        description = "; ".join(light_reading_facts(context))
        return (
            "User-measured light context (a single user measurement, NOT species-level "
            f"evidence; keep it clearly distinct from botanical evidence): {description}. "
            "If this reading influences your recommendation, disclose when and how it was "
            "collected and its reliability, present camera-derived readings as approximate, "
            "and avoid categorical conclusions from one isolated reading."
        )
    return (
        "Light context was relevant to this question, but no eligible user measurement is "
        "available. If the answer materially depends on the plant's actual light exposure, "
        "explain this limitation and recommend obtaining a new light reading."
    )


__all__ = [
    "SUPPORTED_LIGHT_SOURCES",
    "is_light_measurement_eligible",
    "light_context_from_measurement",
    "light_context_observation_text",
    "light_reading_facts",
]
