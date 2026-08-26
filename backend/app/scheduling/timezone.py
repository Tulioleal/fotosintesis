from __future__ import annotations

from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class InvalidTimezoneError(ValueError):
    """Raised when a submitted timezone is not a valid IANA zone name."""


class NonexistentLocalTimeError(ValueError):
    """Raised when a local wall-clock time falls inside a DST spring-forward gap."""


def resolve_timezone(value: str | None) -> ZoneInfo | None:
    """Return a validated ``ZoneInfo`` for an IANA timezone name.

    Returns ``None`` when the value is empty so callers can fall back to the
    user preference. Raises ``InvalidTimezoneError`` for unknown zone names.
    """
    if value is None or not value.strip():
        return None
    try:
        return ZoneInfo(value.strip())
    except (ZoneInfoNotFoundError, ValueError) as error:
        raise InvalidTimezoneError(
            "Provide a valid IANA timezone (for example, America/Argentina/Buenos_Aires)."
        ) from error


def local_datetime_to_utc(due_date: date, due_time: time, zone: ZoneInfo) -> datetime:
    """Convert a local wall-clock date/time to a UTC instant in ``zone``.

    Ambiguous local times (DST fall-back overlap) resolve with the documented
    deterministic rule ``fold=0`` (the earlier offset). Nonexistent local times
    (DST spring-forward gap) raise ``NonexistentLocalTimeError`` listing the
    surrounding valid local times.
    """
    local = datetime.combine(due_date, due_time)
    fold0 = local.replace(tzinfo=zone, fold=0)
    fold1 = local.replace(tzinfo=zone, fold=1)
    roundtripped0 = fold0.astimezone(timezone.utc).astimezone(zone).replace(tzinfo=None)
    roundtripped1 = fold1.astimezone(timezone.utc).astimezone(zone).replace(tzinfo=None)
    if roundtripped0 != local or roundtripped1 != local:
        raise _nonexistent_error(local, zone)
    # Ambiguous (fall-back overlap) or normal: apply the documented earlier
    # offset (fold=0), which for normal times is the only offset.
    return fold0.astimezone(timezone.utc)


def _nonexistent_error(local: datetime, zone: ZoneInfo) -> NonexistentLocalTimeError:
    previous_hour = (local.replace(tzinfo=zone, fold=0) - _one_hour()).astimezone(zone)
    next_hour = (local.replace(tzinfo=zone, fold=0) + _one_hour()).astimezone(zone)
    return NonexistentLocalTimeError(
        f"The selected time does not exist in {zone.key} because of daylight saving time. "
        f"Choose a time such as {previous_hour.strftime('%H:%M')} or {next_hour.strftime('%H:%M')}."
    )


def _one_hour() -> object:
    from datetime import timedelta

    return timedelta(hours=1)
