"""Shared reminder scheduling validation used by the reminders API and the
assistant chat creation path so both surfaces enforce identical rules."""

from __future__ import annotations

from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

from app.scheduling.timezone import local_datetime_to_utc, resolve_timezone


class ReminderValidationError(ValueError):
    """Raised when a reminder schedule violates a validation rule (English message)."""


class MissingReminderTimezoneError(ValueError):
    """Raised when no effective timezone is available to resolve the schedule."""


def resolve_effective_timezone(
    *,
    override: str | None,
    user_timezone: str | None,
) -> ZoneInfo:
    """Resolve the reminder override else the stored user timezone."""
    zone = resolve_timezone(override or user_timezone)
    if zone is None:
        raise MissingReminderTimezoneError(
            "Provide a timezone on your account or on this reminder to schedule it."
        )
    return zone


def ensure_future_due(*, due_date: date, due_time: time, zone: ZoneInfo) -> datetime:
    """Convert local date/time to UTC and require it to be in the future."""
    due_at = local_datetime_to_utc(due_date, due_time, zone)
    if due_at <= datetime.now(timezone.utc):
        raise ReminderValidationError("The date and time must be in the future.")
    return due_at


__all__ = [
    "MissingReminderTimezoneError",
    "ReminderValidationError",
    "ensure_future_due",
    "resolve_effective_timezone",
]
